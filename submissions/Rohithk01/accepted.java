import java.util.*;

public class Main {
    static long f(long n) {
        return n * (n + 1) * (2 * n + 1) / 6;
    }

    static long findN(long k) {
        long lo = 1, hi = 1512307;
        while (lo <= hi) {
            long mid = (lo + hi) >>> 1;
            long v = f(mid);
            if (v == k) return mid;
            if (v < k) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }

    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        int T = sc.nextInt();
        while (T-- > 0) {
            long k = sc.nextLong();
            System.out.println(findN(k));
        }
    }
}