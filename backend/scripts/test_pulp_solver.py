import pulp

def test():
    print("Testing PuLP solver...")
    prob = pulp.LpProblem("Test", pulp.LpMinimize)
    x = pulp.LpVariable("x", lowBound=0)
    y = pulp.LpVariable("y", lowBound=0)
    prob += x + y
    prob += x + 2*y >= 10
    prob += 2*x + y >= 8
    
    status = prob.solve()
    print("Status:", pulp.LpStatus[status])
    print("x:", pulp.value(x))
    print("y:", pulp.value(y))

if __name__ == "__main__":
    test()
