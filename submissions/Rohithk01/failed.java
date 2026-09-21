// ========================================================
// VERDICT: WRONG_ANSWER (Failed on test 1)
// Submission ID: 342362690 | Runtime: 109 ms | Memory: 0 MB
// ========================================================

import java.util.Scanner;
import java.io.*;
import java.util.*;

public class Main {
    public static long myfunction(long fn){
    //(n^2 + n)(2n+1)/6 = fn
    //2n^3 + n^2 + 2n^2 + n = 6*fn
    // 2n^3 + 3n^2 + n
        long n = 1;
        fn *= 6;
        while(fn > 0){
            fn -= ((n*n) + n)*((2*n) + 1);
            if(fn == 0) break;
            n++;
        }
        return n;
    }
    public static void main(String[] args){
        Scanner scanner = new Scanner(System.in);
        int lines = scanner.nextInt();
        for(int i = 0; i < lines; i++){
            long fn = scanner.nextLong();
            long result = myfunction(fn);
            System.out.println(result);
        }
    }
}