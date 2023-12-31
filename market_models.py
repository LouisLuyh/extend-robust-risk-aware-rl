# -*- coding: utf-8 -*-
"""market_models.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1rSYBYqVYslnWyJjtYTsaVT6jwIl-1oIP
"""

import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
import seaborn as sns
import pandas as pd
from pandas_datareader import data as pdr
from sklearn.linear_model import LinearRegression
import random
from datetime import datetime, timedelta



# abstract base class for simulation engine of market models
# requires an instance of MarketModel_Params class as input
# Sim() method is market model dependent and will need to be overrided for each market model
# PlotSim() method plots 100 sample paths with the 10th, 50th, and 90th quantiles overlayed on top
class MarketModel:

  def __init__(self, params):
    self.params = params

  def Sim(self, sim_params):
    raise Exception("Must be overridden in subclass.")

  def PlotSim(self):
    S, t = self.S, self.t
    Nassets = S.shape[2]
    plt.figure(figsize=(5*Nassets, 5))
    plt.rcParams.update({'font.size': 16})
    plt.rc('axes', labelsize=22)
    for i in range(Nassets):
      plt.subplot(1, Nassets, i+1)
      plt.fill_between(t, np.quantile(S[:,:,i], 0.1, axis=1).T, np.quantile(S[:,:,i], 0.9, axis=1).T, color='y', alpha=0.5)
      # plot first 100 paths
      plt.plot(t, S[:,:100,i], linewidth=0.3)
      # plot first path in a thicker line
      plt.plot(t, S[:,0,i], color='r', linewidth=1.5)
      # plot the 10th, 50th and 90th quantiles
      plt.plot(t, np.quantile(S[:,:,i],[0.1, 0.5, 0.9],axis=1).T, color='k', linewidth=1, linestyle='--')
      plt.xlabel("t")
      plt.ylabel("$S_t^" +str(i+1)+"$")

    plt.tight_layout()
    plt.show()

# implementation of one period factor model
class Factor(MarketModel):

  def __init__(self, params = None):
    MarketModel.__init__(self, params)
    self.t = 1

  def Sim(self, sim_params):
    _, _, Nsims, Nassets, _, _, _ = sim_params.GetParams()
    # systematic risk factor common to all asset has normal distribution N(0, 0.02)
    sys_risk = np.random.normal(0, 0.02, (Nsims, 1))
    # idiosyncratic risk factor for asset i has normal distribution  N(0.03*i, 0.025*i)
    idio_risk = np.zeros((Nsims, Nassets))
    for i in range(1, Nassets + 1):
      idio_risk[:, i - 1] = np.random.normal(0.03 * i, 0.025 * i, Nsims)
    # asset returns are composed of systematic risk factor + idiosyncratic risk factor
    self.S = sys_risk + idio_risk
    # insert time dimension to S for consistency
    self.S = np.expand_dims(self.S, axis=0)

    return self.S

# Implementation of the SIR_CEV market model
class SIR_CEV(MarketModel):

  def __init__(self, params):
    MarketModel.__init__(self, params)

  def BondPrice(self, r, tau):
    params = self.params.params
    kappa = params["Q"]["kappa"]
    theta_r = params["Q"]["theta_r"]
    sigma_r = params["Q"]["sigma_r"]
    B = (1 -np.exp(-kappa*tau))/kappa
    A = np.exp((theta_r-sigma_r**2/(2*kappa))*(B - tau) - (sigma_r*B)**2/(4*kappa))
    return A*np.exp(-B*r)

  def Sim(self, sim_params, measure = "P"):
    # load params
    market_params = self.params
    params = market_params.params
    mu, sigma, beta, rho, r0, kappa, theta_r, sigma_r = market_params.GetParams(measure)
    Ndt, T, Nsims, Nassets, S0, X0, phi = sim_params.GetParams()
    rho_inv = np.linalg.inv(rho)

    # general initializations
    t = np.linspace(0, T, Ndt+1)
    dt = t[1] - t[0]
    sqrt_dt = np.sqrt(dt)
    r = np.zeros((Ndt + 1, Nsims))
    r[0, :] = r0

    # used to change from P->Q
    # (a0 - a1 * r)/sigma_r is the drift correction for IR
    a0 = params["P"]["kappa"]*params["P"]["theta_r"]-params["Q"]["kappa"]*params["Q"]["theta_r"]
    a1 = params["P"]["kappa"]-params["Q"]["kappa"]
    sigma_r_eff = sigma_r*np.sqrt((1-np.exp(-2*kappa*dt))/(2*kappa*dt))

    # equity assets let last asset be the bond
    # S has dimensions time, number of simulations, number of assets
    S = np.zeros((Ndt+1, Nsims, len(S0)+1))
    S[0, :, :len(S0)] = S0
    S[0, :, -1] = self.BondPrice(r0, T)

    # initialize benchmark
    X = np.zeros((Ndt+1, Nsims))
    X[0, :] = X0

    # initialize SDF
    Z = np.zeros((Ndt+1, Nsims))
    Z[0, :] = 1
    W = np.zeros((Ndt+1, Nsims, len(S0)+1))
    mpr = np.zeros((Nsims, len(S0)+1))

    for i in range(Ndt) :
      # compute the market-price-of-risk
      eff_vol = sigma * S[i, :, :len(S0)]**beta
      mpr[:, :len(S0)] = (params["P"]["mu"].reshape(1,-1)-r[i, :].reshape(-1,1))/eff_vol
      mpr[:, -1] = (a0 - a1 * r[i, :])/sigma_r
      mpr = mpr @ rho_inv

      # determine Brownian motions...
      dW = sqrt_dt*np.random.multivariate_normal(np.zeros(len(S0)+1), rho, Nsims)
      if measure == "Q":
          dW -= (mpr @ rho) * dt
      W[i, : , :] = dW

      # update interest rate
      r[i+1, :] = theta_r + (r[i, :]-theta_r)*np.exp(-kappa*dt) + sigma_r_eff*dW[:, -1]

      # update the SDF
      Lambda = np.sum(mpr*(rho @ mpr.T).T, axis=1)
      Z[i+1, :] = Z[i, :]* np.exp( -(r[i, :]+0.5*Lambda)*dt - np.sum(dW* mpr, axis=1))

      # update risky assets (excluding the bond)
      S[i+1, :, :len(S0)] = S[i, :, :len(S0)]*np.exp((mu - 0.5 * eff_vol**2)*dt + eff_vol * dW[:, :len(S0)])
      # adjustment factor to ensure martingale
      S_adj_factor = (S0 - np.mean(S[i+1, :, :len(S0)] * Z[i+1, :].reshape(-1, 1), axis = 0))/np.mean(Z[i+1, :])
      S[i+1, :, :len(S0)] += S_adj_factor

      # update the bond
      S[i+1, :, -1] = self.BondPrice(r[i+1, :], T-t[i+1])
      # adjustment factor to ensure martingale
      bond_adj_factor = (S[0, :, -1] - np.mean(S[i+1, :, -1]* Z[i+1, :]))/np.mean(Z[i+1, :])
      S[i+1, :,-1] += bond_adj_factor

      # compute effective volatilities with portfolio positions
      B = (1-np.exp(-kappa*(T-t[i])))/kappa
      phi_eff_vol = phi*np.concatenate((eff_vol, -sigma_r*B*np.ones((Nsims,1))), axis=1)

      # convexity correction term from Ito's lemma
      upsilon =  np.sum(phi_eff_vol*(rho @ phi_eff_vol.T).T, axis=1)
      bond_drift = r[i, :] - B*(a0-a1*r[i, :])
      mu_all = np.concatenate((mu*np.ones((Nsims,1)), bond_drift.reshape(-1,1)), axis=1)

      # update the portfolio value
      X[i+1, :] = X[i, :]* np.exp((r[i, :] + np.sum(phi * (mu_all-r[i, :].reshape(-1,1)), axis=1) \
                                  -0.5*upsilon)*dt + np.sum(phi_eff_vol*dW, axis=1))
      # adjustment factor to ensure martingale
      X_adj_factor = (X0 - np.mean(X[i+1, :] * Z[i+1, :]))/ np.mean(Z[i+1, :])
      X[i+1, :] += X_adj_factor

    self.t, self.S, self.X, self.Z, self.W, self.r = t, S, X, Z, W, r
    return t, S, X, Z, W, r

# Implementation of One Asset Ornstein-Uhlenbeck (OU) process
class Ornstein_Uhlenbeck(MarketModel):

  def __init__(self, params):
    MarketModel.__init__(self, params)

  def Sim(self, sim_params):
    # load params
    sigma, kappa, theta = self.params.GetParams()
    # sigma: stdev of price
    # kappa: damping coefficient
    # theta: long term average/return

    Ndt, T, Nsims, _, S0, _, _= sim_params.GetParams()
    t = np.linspace(0, T, Ndt+1)
    dt = t[1] - t[0]
    sqrt_dt = np.sqrt(dt)
    Nassets = 1
    # S has dimensions time, number of simulations, number of assets
    S = np.zeros((Ndt + 1, Nsims, Nassets))
    S[0, :, 0] = S0
    # calculate effective volatility
    sigma_eff = sigma * np.sqrt((1-np.exp(-2*kappa*dt)) / (2*kappa))
    # update risky asset prices
    for i in range(Ndt) :
      W = np.random.standard_normal((Nsims, Nassets))
      S[i+1, : , :] =  theta + (S[i, :, :] - theta) * np.exp(-kappa*dt) + sigma_eff * W

    self.t, self.S = t, S
    return t, S


class Extended_Ornstein_Uhlenbeck(MarketModel):

  def __init__(self, params):
    MarketModel.__init__(self, params)


  def Sim(self, sim_params):
    # load params
    sigma, kappa = self.params.GetParams()
    """
    :param sigma: standard deviation of price
    :param kappa: damping coefficient
    """

    # switch S0 to wild card
    Ndt, T, Nsims, Nassets, S0, _, _ = sim_params.GetParams()
    t = np.linspace(0, T, Ndt + 1)
    dt = t[1] - t[0]
    sqrt_dt = np.sqrt(dt)

    # systematic risk factor common to all asset has normal distribution N(0, 0.02)
    sys_risk = np.random.normal(0, 0.02, (Nsims, 1))

    # idiosyncratic risk factor for asset i has normal distribution N(0.03*i, 0.025*i) // set mu := 1+0.03i
    idio_risk = np.zeros((Nsims, Nassets))
    for i in range(1, Nassets+1):
      idio_risk[:, i-1] = np.random.normal(1+0.03*i, 0.025*i, Nsims)

    theta = sys_risk + idio_risk

    # S has dimensions price w.r.t. time, number of simulations, number of assets
    S = np.zeros((Ndt + 1, Nsims, Nassets))

    # ToDO: re-construct S0 (or assume all stock price start at 1)
    # set the start price of all stocks = 1
    for i in range(Nassets):
      S[0, :, i] = S0

    """
    in order to hard code S0=1, theta should also be price instead of return percentage
    
    """

    # calculate effective volatility
    sigma_eff = sigma * np.sqrt((1 - np.exp(-2 * kappa * dt)) / (2 * kappa))
    # update risky asset prices
    for i in range(Ndt):
      W = np.random.standard_normal((Nsims, Nassets))
      S[i + 1, :, :] = theta + (S[i, :, :] - theta) * np.exp(-kappa * dt) + sigma_eff * W


    self.t, self.S = t, S
    return t, S
    
    
class Extended_Ornstein_Uhlenbeck_BearMarket(MarketModel):

  def __init__(self, params):
    MarketModel.__init__(self, params)

  def Sim(self, sim_params):
    sigma, kappa = self.params.GetParams()

    Ndt, T, Nsims, Nassets, S0, _, _ = sim_params.GetParams()
    t = np.linspace(0, T, Ndt + 1)
    dt = t[1] - t[0]
    sqrt_dt = np.sqrt(dt)

    sys_risk = np.random.normal(0, 0.02, (Nsims, 1))
    idio_risk = np.zeros((Nsims, Nassets))
    for i in range(1, Nassets + 1):
      idio_risk[:, i - 1] = np.random.normal(1 - 0.03 * i, 0.025 * i, Nsims)

    theta = sys_risk + idio_risk
    S = np.zeros((Ndt + 1, Nsims, Nassets))
    for i in range(Nassets):
      S[0, :, i] = S0

    sigma_eff = sigma * np.sqrt((1 - np.exp(-2 * kappa * dt)) / (2 * kappa))
    for i in range(Ndt):
      W = np.random.standard_normal((Nsims, Nassets))
      S[i + 1, :, :] = theta + (S[i, :, :] - theta) * np.exp(-kappa * dt) + sigma_eff * W

    self.t, self.S = t, S
    return t, S


class RealData(MarketModel):

  def __init__(self, data):
    self.data = data

  def Sim(self, sim_params):
    data = self.data
    Ndt, T, Nsims, Nassets, _, _, _ = sim_params.GetParams()

    # make market price data numerically indexed
    data = data.reset_index(drop=True)
    # compute feasible start dates
    latest_start_date = data.shape[0]-1-Ndt
    feasible_start_date = np.array(data.loc[:latest_start_date].index)
    # sample from feasible start dates
    sample_start_date = np.random.choice(feasible_start_date, size=Nsims, replace=True)

    # create the price matrix and fill up with random sample data between start_date and start_date + Ndt
    S = np.zeros((Ndt + 1, Nsims, Nassets))
    for i in range(Nsims):
      S[:, i, :] = np.array(data.loc[sample_start_date[i]: sample_start_date[i]+Ndt])
      # normalize price over the trade period
      S[:, i, :] = S[:, i, :] / S[0, i, :]

    t = np.linspace(0, T, Ndt + 1)

    self.t, self.S = t, S
    return t, S