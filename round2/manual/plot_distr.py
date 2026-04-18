import matplotlib.pyplot as plt
import numpy as np

BUDGET = 100
SPEED = 10
SPEED_MUL = 0.2

def research(x):
    return 200_000 * np.log(1 + x) / np.log(1 + 100)

def scale(x):
    return (x/100) * 7

#C is cost left after speed investment

def crunch(C):
    x = np.arange(0, C, 1)
    y1 = list(map(research, x)) #x is research invest
    y2 = list(map(scale, C-x)) #x+y = C, y is scale invest
    ynet = [y1[i] * y2[i] * SPEED_MUL - 50000*BUDGET/100 for i in range(len(y1))]

    plt.plot(x, ynet, label=f"C={C}")

crunch(BUDGET - SPEED)

plt.legend()
plt.show()