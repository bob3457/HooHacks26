## Inspiration
We were interested by the concept of price hedging in agriculture.

## What it does
Prices in agriculture are largely inelastic, due to the production cycle being highly time-sensitive (seasonal crops). As a result, farmers have few protections against price fluctuations. There exist loans and financial instruments in place, but what if a farmer knew about price fluctuations before they even happen?

Our goal with foreGASt is to use natural gas prices, coal prices, and 

## How we built it
First,

## Challenges we ran into
- Our initial model struggled with the massive 2021-2022 Ukraine fertilizer price spikes. When tested on the 2023-2024 stabilization period, the AI hallucinated massive upward swings because it was over-weighting the 2022 volatility, resulting in an essentially coin flip accuracy. We solved this by reducing our recency-weighting multipliers, switching our classifier to a binary:logistic objective, and forcing the model to learn fundamentals rather than panicking over outliers.
- Halfway through the hackathon, we realized that everyone had a different version of how we wanted to implement our product and lacked the cohesiveness that we wanted. We sat down and spent an hour ensuring that everyone was on the same page, resulting in increased productivity.
## Accomplishments that we're proud of
 - Our model is able to predict the price of fertilizer in 90 days with a 75% accuracy, averaged over 50 training samples. Considering the lack of uniform data and noise in our data, and the lack of resources we have to access much cleaner data behind a paywall, we are proud of the model's performance.
## What we learned
1. Yogeshwar - I really enjoyed developing and working on improving this model and integrating it into the frontend. I didn't have much financial knowledge, and I really enjoyed taking my ML skills and applying it to a new domain!

## What's next for foreGASt
