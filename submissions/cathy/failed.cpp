#include <iostream>
using namespace std;

int grid[8][8];
int n;
int rowSums[8];
int currRowSums[8];
int currColSums[8];
int colSums[8];

bool dfs(int x, int y) {
    if (x == n) {
        for (int i = 0; i < n; i++) {
            if (rowSums[i] != currRowSums[i] || colSums[i] != currColSums[i]) {
                return false;
            }
        }
        return true;
    }

    if ((currRowSums[x] == rowSums[x]) ^ (currColSums[y] == colSums[y])) {
        return false;
    }

    if (currRowSums[x] < rowSums[x] && currColSums[y] < colSums[y]) {
        grid[x][y] = 1;
        currRowSums[x]++;
        currColSums[y]++;

        bool check = false;
        if (currRowSums[x] == rowSums[x]) {
            // skip to next row, tbh
            check |= dfs(x+1, 0);
        } else if (y == n-1) {
            check |= dfs(x+1, 0);
        } else {
            check |= dfs(x, y + 1);
        }

        if (check) {
            return true;
        }

        grid[x][y] = 0;
        currRowSums[x]--;
        currColSums[y]--;
    }

    bool check = false;
    if (y == n-1) {
        check |= dfs(x+1, 0);
    } else {
        check |= dfs(x, y + 1);
    }

    if (check) {
        return true;
    }
    return false;
}

int main() {
    cin >> n;

    for (int i = 0; i < n; i++) {
        cin >> colSums[i];
    }
    for (int i = 0; i < n; i++) {
        cin >> rowSums[i];
    }


    dfs(0, 0);

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            cout << grid[i][j];
        }
        cout << endl;
    }

}