"""Main application entry point"""


def hello_world(name: str = "World") -> str:
    """
    Simple greeting function.
    
    Args:
        name: Name to greet
        
    Returns:
        Greeting message
    """
    return f"Hello, {name}!"


def main():
    """Application entry point"""
    message = hello_world("User")
    print(message)


if __name__ == "__main__":
    main()
