#include <iostream>
using namespace std;

int n;
int r_rem[8], c_rem[8];
int grid[8][8];

bool dfs(int i, int j) {
    if (i == n) return true;


    // prepare for next iteration
    int ni = i, nj = j + 1;
    if (nj == n) {
        ni++;
        nj = 0;
    }

    // Try placing 0
    {
        // check: can we still fulfill row i?
        int remaining_cells_row = n - j - 1;
        if (r_rem[i] <= remaining_cells_row) {
            // check: can column j still reach its target?
            int remaining_cells_col = n - i - 1;
            if (c_rem[j] <= remaining_cells_col) {
                grid[i][j] = 0;
                if (dfs(ni, nj)) return true;
            }
        }
    }

    // Try placing 1
    if (r_rem[i] > 0 && c_rem[j] > 0) {
        grid[i][j] = 1;
        r_rem[i]--;
        c_rem[j]--;

        if (dfs(ni, nj)) return true;

        // undo
        r_rem[i]++;
        c_rem[j]++;
    }

    return false;
}

int main() {
    cin >> n;

    for (int i = 0; i < n; i++) cin >> c_rem[i];
    for (int i = 0; i < n; i++) cin >> r_rem[i];

    dfs(0, 0);

    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            cout << grid[i][j];
        }
        cout << "\n";
    }
}