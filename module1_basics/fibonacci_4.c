/******************************************************
 * Program: Recursive Fibonacci Sequence in C
 * Author: Miroslaw Staron
 * Generated with the assistance of ChatGPT
 * 
 * Description:
 *   This program computes Fibonacci numbers using
 *   a recursive implementation. The user provides
 *   how many terms should be generated, and the
 *   program prints the sequence to the console.
 * 
 * Notes:
 *   - Recursive implementation is elegant but may
 *     be inefficient for large inputs.
 *   - For performance, memoization or iteration
 *     should be considered in real-world systems.
 * 
 * Additional Information:
 *   This code was generated with ChatGPT and is 
 *   shared in the context of research and teaching.
 *   For more information about software engineering 
 *   research and industry collaboration, please visit:
 *   https://software-center.se
 ******************************************************/

#include <stdio.h>  

// Recursive function to calculate Fibonacci number at position n
int fibonacci(int n) {  

    // Base case: if n is 0, return 0
    if (n == 0)  
        return 0;  

    // Base case: if n is 1, return 1
    else if (n == 1)  
        return 1;  

    // Recursive case: sum of previous two terms
    else  
        return fibonacci(n - 1) + fibonacci(n - 2);  
}  

int main() {  

    // Variable to store number of terms requested by the user
    int terms;  

    // Ask user for input
    printf("Enter the number of terms: ");  

    // Read input from user
    scanf("%d", &terms);  

    // Check if input is valid
    if (terms <= 0) {  

        // Error message if not valid
        printf("Please enter a positive integer.\n");  
    }  
    else {  

        // Print header message
        printf("Fibonacci Sequence up to %d terms:\n", terms);  

        // Loop through and print each Fibonacci number
        for (int i = 0; i < terms; i++) {  

            // Call recursive function and print result
            printf("%d ", fibonacci(i));  
        }  

        // Print newline after sequence
        printf("\n");  
    }  

    // Exit program successfully
    return 0;  
}
