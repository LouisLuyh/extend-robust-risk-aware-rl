# Robust Risk-Aware Reinforcement Learning (RRA-RL) Applied in Dynamic Asset Allocation

Sahana Ramesh, Yiheng Lu, Shaswat Srivastava, Ziwei Duan & Jun Jie Ou Yang

## Research Extended From: 

<I>Robust Risk-Aware Reinforcement Learning by Sebastian Jaimungal, Silvana Pesenti, Ye Sheng Wang, and Hariom Tatsat </I>

Reference: <a>[Github](https://github.com/sebjai/robust-risk-aware-rl)</a>, <a>[Paper](https://arxiv.org/abs/2108.10403)</a>

## Directory

The *.ipynb files here implemented the example problem extended from the paper and the validation for the implementation of the example

<a>[Link to Colab](https://drive.google.com/drive/folders/1EJk-y5jg7dYjxzlbvCXizAMuhPa41Nlh?usp=drive_link)</a>

- **Example_4_Robust_Portfolio_Allocation_w_Dynamic_Trading**: using the EOU model, trained on simulated data
  - **Example_4_graphs** (performance comparison with different risk preferences **P**)
- **Example_5_Robust_PA_w_DT_Real_Data**: using the realData Model, trained on bull market data
  - **Example_5_for_bear_market**: using the realData Model, trained on bear market data
- **Example_Validations_Bull**: validating on a bull market
- **Example_Validations_Bear**: validating on a bear market

## Procedure:
- Mount to the GDrive
- Run **Example_4_Robust_Portfolio_Allocation_w_Dynamic_Trading** to train the simulated data model (EOU) on simulated data. It would save the Weights of allocation for the last five epochs, the terminal value of the portfolio for each epoch, and the daily portfolio value for the last five epochs (with 6 P-values, in ex4the  folder).
- Run **Example_5_Robust_PA_w_DT_Real_Data** to train the realData model (realData) on the bull market data.  It would save the Weights of allocation for the last five epochs, the terminal value of the portfolio for each epoch, and the daily portfolio value for the last five epochs (with 6 P-values, in the ex5(v2) folder).
- Run **Example_5_for_bear_market** to train the realData model (realData) on the bear market data.  It would save the Weights of allocation for the last five epochs, the terminal value of the portfolio for each epoch, and the daily portfolio value for the last five epochs (with 6 P-values, in the ex5(bear) folder). 
  - With T4 GPU, takes 3100 seconds for each P-value with 150 epochs
- After training, run **Example_Validations_Bull**/**Example_Validations_Bear** that loads the benchmark results and validates the produced results
