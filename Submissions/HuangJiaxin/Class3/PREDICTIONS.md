# Predictions (written before the full measurements)

Written by Jiaxin Huang on 27 November 2026, before running `run_lab.py`. Known at this
point: N = 8,760 periods for one year and 43,822 for five years; the machine has 3 GB of
memory; Bitcoin went from about 109,600 to about 77,600 USDT over the last year. The
three-period hand trace (TRACE.md) was done before these predictions.

The AI gave hints on how to reason (Theta(N^2) growth, bytes per number); the answers
are mine. My first answers to questions 1 and 4 were wrong and are kept below with the
correction, because the mistake is part of what I learned.

| # | Question | My prediction | Reason |
|---|---|---|---|
| 1 | Five years vs one year: how many times longer? | **25 times** | The work is Theta(N^2); N is about 5 times larger, so the time is about 5^2 = 25 times. (First I wrote "x to the power 5"; that confuses the growth factor with an exponent.) |
| 2 | How much faster is numpy than plain Python? | **Tens of times** | Plain Python handles one node at a time and checks types at every step; numpy does a whole date at once in compiled code. |
| 3 | Two arrays, 40 assets, five years: is 3 GB enough? | **Yes** | Two arrays of 43,823 numbers at 8 bytes are about 700,000 bytes, far below 3 GB, and the assets are priced one after another. |
| 4 | Full tree: memory when N doubles? | **4 times** | The tree has about N^2/2 nodes; (2N)^2 / N^2 = 4. (First I wrote "N^2 times"; the factor does not depend on N.) |
| 5 | Is the American put worth more than the European one, and by how much? | **Yes; the premium is about as large as on the hand-traced tree (one third of the value) or larger** | Bitcoin is very volatile, so the right to exercise early should be valuable. |
| 6 | Would the holder of the Bitcoin put have exercised early in the last year? | **Yes** | Bitcoin fell from about 109,600 to 77,600; when the price falls deep enough, exercising now is better than waiting (as at t = 1 and t = 2 in my hand trace). |
