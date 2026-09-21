#include <iostream>
#include <climits>
#include <cmath>
// i/o optimization

using namespace std;

// get k where k = f(n)
long long getK (long long n) {
    return (long long)((__int128)n * (n + 1) * (2 * n + 1) / 6);
}

// find index of n by searching for it in a binary manner
int bSearch (long long k) {
    long long low = 1, high = 2000000;
    
    while (low <= high) {
        long long mid = low + (high - low) / 2;
    
        long long maybeK = getK(mid);
        if (maybeK > k) { // this k val is too high, n must be lower, decr high
            high = mid - 1;
        } else if (maybeK < k) { // too low k val, n must be higher, incr low
            low = mid + 1;
        } else { // maybeK == k
            return mid; // we found n!
        }
    }
    return -1;
    
}


int main() {
    // FIRST PROBLEM IDK WHY IT NO WORK :(
    ios::sync_with_stdio(false);
    cin.tie(nullptr);
    
    int t;
    cin >> t;
    while (t--) {
        long long k;
        cin >> k;
        int n = bSearch(k);
        cout << n << endl;
    }
    return 0;
}