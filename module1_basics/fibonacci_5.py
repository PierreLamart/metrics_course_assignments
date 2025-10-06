"""
******************************************************
 Program: Recursive Fibonacci Sequence in Python
 Author: Miroslaw Staron
 Generated with the assistance of ChatGPT
 
 Description:
   This program computes Fibonacci numbers using
   a recursive implementation. The user provides
   how many terms should be generated, and the
   program prints the sequence to the console.
 
 Notes:
   - Recursive implementation is elegant but may
     be inefficient for large inputs.
   - For performance, memoization or iteration
     should be considered in real-world systems.
 
 Additional Information:
   This code was generated with ChatGPT and is 
   shared in the context of research and teaching.
   For more information about software engineering 
   research and industry collaboration, please visit:
   https://software-center.se
******************************************************
"""

# Recursive function
def fibonacci(n): return 0 if n == 0 else 1 if n == 1 else fibonacci(n-1)+fibonacci(n-2)

def main():
    terms = int(input("Enter the number of terms: "))
    if terms <= 0: print("Please enter a positive integer.")
    else:
        print(f"Fibonacci Sequence up to {terms} terms:")
        for i in range(terms): print(fibonacci(i), end=" ")
        print()

if __name__ == "__main__": main()
