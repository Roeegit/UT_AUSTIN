//
// Created by zara on 10/6/25.
//

#include <iostream>
using namespace std;
int main() {
    // FIRST PROBLEM IDK WHY IT NO WORK :(
    int numTests;
    cin >> numTests;
    // each line contains single integer k
    // print line with pos int n where f(n) = k
    // k = (n(n + 1)(2n + 1))/6

    while (numTests--) {
        long long contender;
        cin >> contender; // take in numTest
        long long square = 2;
        while (contender - 1 > 0) {
            contender -= square * square;
            square++;
        }
        cout << (--square) << endl;
    }
    return 0;

    // int totalPounds, numTypes;
    // cin >> totalPounds >> numTypes;
    // // numTypes is also n
    // int n = numTypes;
    // while (n--) { // read next n lines
    //     double p;
    //     int k;
    //     cin >> p >> k;
    //
    // }



}
