from src import BaseAirdrop, AirdropConfig, TokenConfig, WalletConfig, RecipientAmount
from rich import print

def test_basic_airdrop():
    print("[bold green]Testing Token Flight Package[/bold green]")
    
    # Create wallet configuration
    wallet_config = WalletConfig(
        node_url="http://localhost:9053",
        network_type="mainnet",
        explorer_url="https://api.ergoplatform.com/api/v1",
        node_api_key="test_key",
        node_wallet_address="test_address",
        wallet_mnemonic=None,
        mnemonic_password=None
    )
    
    # Create token configuration
    token_config = TokenConfig(
        token_name="TestToken",
        total_amount=1000000,
        amount_per_recipient=None,
        min_amount=0.001,
        decimals=0,
        recipients=[
            RecipientAmount(
                address="9f4QF8AD1nQ3nJahQVkMj8hFSVVzVom77b52JU7EW71Zexg6N8f",
                amount=100
            ),
            RecipientAmount(
                address="9h3DKaZhYUD7XQXm8EoRBzVqzNftGxF92GqMPCYGQFBRpDyGtks",
                amount=200
            )
        ]
    )
    
    try:
        # Create airdrop configuration
        config = AirdropConfig(
            wallet_config=wallet_config,
            tokens=[token_config],
            min_hashrate=0,
            debug=True,
            headless=True,
            recipients_file=None,
            recipient_addresses=None
        )
        
        # Initialize airdrop
        airdrop = BaseAirdrop(config=config)
        print("[green]✓[/green] Successfully created Airdrop instance")
        
        print("\n[bold blue]Airdrop Configuration:[/bold blue]")
        print(f"Token Name: {token_config.token_name}")
        print(f"Total Amount: {token_config.total_amount}")
        print(f"Number of Recipients: {len(token_config.recipients)}")
        print(f"Debug Mode: {config.debug}")
        
    except Exception as e:
        print(f"[red]Error:[/red] {str(e)}")

if __name__ == "__main__":
    test_basic_airdrop() 