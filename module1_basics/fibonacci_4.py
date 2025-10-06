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

# Recursive function to calculate Fibonacci number at position n
def fibonacci(n):

    # Base case: if n is 0, return 0
    if n == 0:
        return 0

    # Base case: if n is 1, return 1
    elif n == 1:
        return 1

    # Recursive case: sum of previous two terms
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)


def main():

    # Ask user for input
    terms = int(input("Enter the number of terms: "))

    # Check if input is valid
    if terms <= 0:

        # Error message if not valid
        print("Please enter a positive integer.")

    else:

        # Print header message
        print(f"Fibonacci Sequence up to {terms} terms:")

        # Loop through and print each Fibonacci number
        for i in range(terms):

            # Call recursive function and print result
            print(fibonacci(i), end=" ")

        # Print newline after sequence
        print()


# Call the main function
if __name__ == "__main__":
    main()
