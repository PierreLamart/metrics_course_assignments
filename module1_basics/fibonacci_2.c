#include <stdio.h>  

// Function to generate Fibonacci numbers
void fibonacci(int n) {  

    // Variable to store the (n-2)th Fibonacci number
    long long first = 0;  
    
    // Variable to store the (n-1)th Fibonacci number
    long long second = 1;  
    
    // Variable to store the current Fibonacci number
    long long next;   

    // Print header message
    printf("Fibonacci Sequence up to %d terms:\n", n);  

    // Loop from 0 to n-1
    for (int i = 0; i < n; i++) {   

        // First two terms (0 and 1) are fixed
        if (i <= 1)                 
            // Directly assign 0 or 1
            next = i;               

        // For other terms
        else {                      
            // Sum of the two previous numbers
            next = first + second;  

            // Move 'second' to 'first'
            first = second;         

            // Move 'next' to 'second'
            second = next;          
        }

        // Print the current Fibonacci number
        printf("%lld ", next);      
    }

    // Print a newline after the sequence
    printf("\n");  
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
        // Call the Fibonacci function
        fibonacci(terms);  
    }

    // Exit program successfully
    return 0;  
}
