from src import Airdrop, TokenConfig, BaseAirdrop
from rich import print

def test_basic_airdrop():
    print("[bold green]Testing Token Flight Package[/bold green]")
    
    # Create a token configuration
    config = {
        "token_id": "test_token_id",
        "total_amount": 1000000,
        "decimals": 0
    }
    
    try:
        # Initialize airdrop
        airdrop = Airdrop(config)
        print("[green]✓[/green] Successfully created Airdrop instance")
        
        # Add some test recipients
        airdrop.add_recipient("9f4QF8AD1nQ3nJahQVkMj8hFSVVzVom77b52JU7EW71Zexg6N8f", 100)
        airdrop.add_recipient("9h3DKaZhYUD7XQXm8EoRBzVqzNftGxF92GqMPCYGQFBRpDyGtks", 200)
        print("[green]✓[/green] Successfully added recipients")
        
        # Build transaction (this won't submit, just build)
        tx = airdrop.build_transaction()
        print("[green]✓[/green] Successfully built transaction")
        
        print("\n[bold blue]Transaction Details:[/bold blue]")
        print(f"Recipients: {len(airdrop.recipients)}")
        print(f"Total Amount: {airdrop.total_amount}")
        
    except Exception as e:
        print(f"[red]Error:[/red] {str(e)}")

if __name__ == "__main__":
    test_basic_airdrop() 