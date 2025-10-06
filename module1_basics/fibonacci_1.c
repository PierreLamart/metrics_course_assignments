#include <stdio.h>

// Function to generate Fibonacci numbers
void fibonacci(int n) {
    long long first = 0, second = 1, next;

    printf("Fibonacci Sequence up to %d terms:\n", n);

    for (int i = 0; i < n; i++) {
        if (i <= 1)
            next = i;
        else {
            next = first + second;
            first = second;
            second = next;
        }
        printf("%lld ", next);
    }
    printf("\n");
}

int main() {
    int terms;

    printf("Enter the number of terms: ");
    scanf("%d", &terms);

    if (terms <= 0) {
        printf("Please enter a positive integer.\n");
    } else {
        fibonacci(terms);
    }

    return 0;
}
