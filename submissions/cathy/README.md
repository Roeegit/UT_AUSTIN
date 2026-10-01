# E. Largest Sorted Partitions

Time limit per test: 1 second
Memory limit per test: 256 megabytes

Given an array A of size N and an integer 1 <= k <= N, we can cut A from left to right into consecutive contiguous subarrays. Each subarray has size k, except possibly the last subarray, which may have size between 1 and k inclusive. Equivalently, we cut after positions k, 2k, 3k, ... until the end of the array. These subarrays, including the last subarray, are the k-partitions of A.

For example, for the array
A = [1, 2, 3, 1, 1, 2, 5]
the 3-partitions of A are [1, 2, 3], [1, 1, 2], and [5].

The array A has sorted k-partitions if each of its k-partitions (including the last partition) has non-decreasing elements. Note that every array has sorted 1-partitions, and that an array of size N has sorted N-partitions if and only if A itself is sorted. The example array A above has sorted k-partitions for k = 1 and 3.

Given an array A of size N, compute the largest integer k <= N for which A has sorted k-partitions.

## Input

The first line of input contains a single integer N (1 <= N <= 2 * 10^5), the size of the input array. The next line contains N space-separated integers a_i (0 <= a_i <= 10^6), the contents of the array.

## Output

Print the largest integer k <= N for which A has sorted k-partitions. Such an integer is always guaranteed to exist.

## Examples

Example 1
Input:
7
1 2 3 1 1 2 5

Output:
3

Example 2
Input:
7
42 42 42 42 42 42 42

Output:
7

Example 3
Input:
5
4 3 2 1 0

Output:
1

## Note

Hint: think about the time complexity of your approach before implementing a solution!