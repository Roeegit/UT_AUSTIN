# D. Interview Flights

**time limit per test:** 1 second  
**memory limit per test:** 256 megabytes  

Congratulations! You've been selected by Conglomo Corp. as a finalist for a summer internship. They are flying you to their headquarters for a final in-person interview.

Some flights are more likely to arrive on time than others, and you want to maximize the probability that you arrive at the interview on time and without missing a connection. Nothing else matters: you are willing to take a longer overall trip with more flight segments if doing so has a higher chance of arriving on time than a shorter itinerary.

Given a list of flights, each of which has a starting city, ending city, and probability of arriving on time, compute the optimal itinerary for arriving at the interview without incident.

## Input

The first line of input contains two space-separated integers $n$ ($2 \le n \le 50000$) and $m$ ($1 \le m \le 50000$): the number of cities the airline serves, and the number of available flights, respectively.

Each of the next $m$ lines describes one flight. A flight consists of two space-separated integers $s$ and $d$ followed by a real number $p$ ($1 \le s, d \le n$, $0.0 \le p \le 1.0$), indicating that a flight exists from city $s$ to city $d$, and that this flight arrives on time with probability $p$. All listed flights are one-way and it is guaranteed that $s \ne d$. There might be multiple flights with the same source and destination city.

City $1$ is Austin and city $n$ is Conglomo Corp. headquarters.

## Output

Print the probability of arriving at your job interview on time, assuming you fly using the optimal itinerary that maximizes this probability. Your answer will be judged correct if it differs from the judge answer with relative or absolute error at most $10^{-4}$.

Assume that flight delays are independent events, so that the probability of arriving at Conglomo Corp. headquarters is the product of the probabilities that all flights along the way arrive on time.

Note that if it is impossible to travel from Austin to Conglomo Corp. headquarters, the probability of arriving on time is $0$.

## Examples

### Example 1

**Input**
```text
3 6
1 3 0.2
1 2 0.9
1 2 0.8
2 3 0.7
3 1 1.0
3 2 0.9