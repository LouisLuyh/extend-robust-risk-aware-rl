# -*- coding: utf-8 -*-
"""metrics.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1t1HrHFXy7NG6LrOX5-y9vHzTR1QrCWWH
"""

import torch

def GetRiskMeasure(X, rm_params):
  alpha, beta, p, rm_type = rm_params.GetParams()
  # calculates the alpha-beta risk measure of batch X
  if rm_type == "alpha-beta":
    # find the alpha and beta quantiles of X
    LQtl = torch.quantile(X, alpha)
    UQtl = torch.quantile(X, beta)
    # normalizing factor
    eta = p * alpha + (1-p) * (1-beta)
    RiskMeasure = -(p * alpha * torch.mean(X[X <= LQtl]) + (1-p) * (1-beta) * torch.mean(X[X >= UQtl])) / eta
        # utility w. distortion
  # calculates mean-CVaR risk measure of batch X
  elif rm_type == "mean-CVaR":
    LQtl= torch.quantile(X, alpha)
    # weighted combination of mean and CVaR with 10x more emphasis on the CVaR
    RiskMeasure = -1/11 * torch.mean(X) - 10/11 * torch.mean(X[X <= LQtl])

  else:
    print("Risk Measure Type Not Supported.")
  
  return RiskMeasure

# Given two tensors X and Y, alongside relevent parameters, return the loss, risk measure of X and Y, and the wass distance
def GetMetrics(X, Y, rm_params, lm_params, wass_params, rm_objective = 'maximize', problem_type = 'inner', device = torch.device('cpu')):
    Nsims = X.shape[0]
    # sort both X and Y so X_sorted and Y_sorted are comonotonic
    X_sorted, _ = torch.sort(X, dim = 0)
    Y_sorted, _ = torch.sort(Y, dim = 0)
    X_sorted_nograd = X_sorted.detach()
    Y_sorted_nograd = Y_sorted.detach()
    # calculate the gradient of the distribution function of Y
    f_y , grad_F_y = GetGradient(Y_sorted)
    # since Y_sorted is sorted, the empirical CDF will be equally spaced in ascending order from 0 to 1
    F_y = torch.linspace(0, 1, Nsims + 1)[1:].reshape(-1, 1).to(device)
    # operations outside of GetGradient() are using the no gradient copies of tensor X and Y
    rank_diff = Y_sorted_nograd - X_sorted_nograd
    wass_order, wass_limit = wass_params.GetParams()
    wass_dist = torch.mean(torch.abs(rank_diff)**wass_order)**(1/wass_order)

    alpha, beta, p, rm_type = rm_params.GetParams()
    # RM_weight is the risk measure contribution to the gradient and depends on the $\gamma$ RM distortion fnc
    if rm_type == 'alpha-beta':
      # eqn 4.1 in paper
      norm_factor = p*alpha + (1-p)*(1-beta)
      RM_weight = (p*(F_y <= alpha)+(1-p)*(F_y > beta))/norm_factor
    
    elif rm_type == 'mean-CVaR':
      RM_weight = 10/11 * (F_y <= alpha)/alpha + 1/11

    else:
      print("Risk Measure Type Not Supported.")
    
    # find the full inner problem gradient using inner gradient formula in paper eqn 3.5
    # the Y input tensor should only have gradients wrt theta as phi is fixed in the inner problem
    if problem_type == "inner":
      lam, mu, _ = lm_params.GetParams()
      constr_err = wass_dist**wass_order - wass_limit**wass_order
      Lambda = (lam + mu*constr_err)*(wass_dist > wass_limit)
      # LM_weight is the wass constraint contribution to the gradient
      LM_weight = wass_order * Lambda * torch.abs(rank_diff)**(wass_order - 1) * torch.sign(rank_diff)

      # loss depends if objective is to maximize or minimize RM
      if rm_objective == "minimize":
        total_weight = RM_weight - LM_weight

      elif rm_objective == "maximize":
        total_weight = -RM_weight - LM_weight
      
      else:
        print("Risk Measure Objective Not Supported.")
      # only grad_F_y contains any gradients
      loss = torch.mean(grad_F_y * total_weight / f_y)
    
    # find the full outer problem gradient using outer gradient formula in paper eqn 3.7
    # the Y input tensor should only have gradients wrt phi as theta is fixed in the outer problem
    elif problem_type == "outer":
      loss = torch.mean(grad_F_y * RM_weight / f_y)

    rm_phi = GetRiskMeasure(X, rm_params)
    rm_theta = GetRiskMeasure(Y, rm_params)

    return loss, rm_phi.item(), rm_theta.item(), wass_dist.item()

def GetGradient(X):
    # calculate the gradient of the distribution function of input X by using the KDE approach
    n = X.shape[0]
    X_no_grad = X.detach()
    normal = torch.distributions.Normal(0,1)
    # bandwith size using a scaled down version of Silverman's rule
    h = 1.06 * torch.std(X_no_grad) * n**(-1/5) / 2
    z_score = (X_no_grad.reshape(1, -1) - X_no_grad.reshape(-1, 1))/h
    f_x = torch.mean(torch.exp(normal.log_prob(z_score)), axis = 0)/h
    # ensure gradients are only attached in calculation of grad_F_x through the X tensor
    grad_F_x = -torch.mean(torch.exp(normal.log_prob(z_score))*X.reshape(-1,1), axis = 0)/h 

    return f_x.reshape(-1, 1), grad_F_x.reshape(-1, 1)