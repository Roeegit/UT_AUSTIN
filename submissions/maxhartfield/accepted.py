import heapq
if __name__ == '__main__':
    n, m = map(int, input().split())
    adjList = [[] for _ in range(n)]
    for _ in range(m):
        s, d, p = input().split()
        s = int(s)
        d = int(d)
        p = float(p)
        adjList[s - 1].append((-p, d - 1))
    heap = [(-1, 0)]
    visited = [False] * n
    while heap:
        p, node = heapq.heappop(heap)
        if node == n - 1:
            print(-p)
            exit()
        if visited[node]:
            continue
        visited[node] = True
        for adj in adjList[node]:
            heapq.heappush(heap, (adj[0] * -p, adj[1]))
    print(0)
