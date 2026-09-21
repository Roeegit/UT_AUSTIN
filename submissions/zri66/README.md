# Problem A: Sum of Squares

**Time limit per test:** 1.0 s  
**Memory limit per test:** 256 MB  

There is a well-known formula for the sum $f(n)$ of the first $n$ squares:

$$f(n) = 1^2 + 2^2 + 3^2 + \dots + n^2 = \frac{n(n + 1)(2n + 1)}{6}$$

Write a program that computes $n$ given $f(n)$.

---

### Input

The first line of input contains a single integer $T$, the number of test cases ($1 \le T \le 10000$).

Each of the following $T$ lines contains a single integer $k$ ($1 \le k \le 2^{60}$).

---

### Output

For each test case, print a line with the positive integer $n$ satisfying $f(n) = k$. It is guaranteed that such an integer exists.

---