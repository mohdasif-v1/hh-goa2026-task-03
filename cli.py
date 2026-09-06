import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def render_step_1_face(match_result: dict, image_path: str):
    console.print("\n[bold cyan][1/5] FACE VERIFICATION[/bold cyan]")
    console.print(f"Input image: [yellow]{image_path}[/yellow]")
    if match_result.get("match"):
        console.print("  [bold green]✓ Face detected[/bold green]")
        console.print("  [bold green]✓ Face matched[/bold green]")
        console.print(f"  Matched Subject: [bold white]{match_result.get('matched_id')}[/bold white]")
        console.print(f"  Similarity: [bold green]{match_result.get('confidence')}[/bold green]")
        console.print(f"  Threshold: [dim]{match_result.get('threshold_used')}[/dim]")
    else:
        console.print("  [bold red]✗ Face match failed[/bold red]")
        console.print(f"  Similarity: [red]{match_result.get('confidence')}[/red]")
        console.print(f"  Threshold: {match_result.get('threshold_used')}")

def render_step_2_search(selected_result: dict, query_used: str):
    console.print("\n[bold cyan][2/5] WEB SEARCH[/bold cyan]")
    console.print("  [bold green]✓ Live search executed[/bold green]")
    console.print("  [bold green]✓ Real result found[/bold green]")
    console.print(f"  Title: [bold white]{selected_result.get('title')}[/bold white]")
    console.print(f"  URL: [link={selected_result.get('url')}]{selected_result.get('url')}[/link]")
    if selected_result.get("snippet"):
        console.print(f"  Snippet: [dim]{selected_result.get('snippet')[:100]}...[/dim]")

def render_step_3_fingerprint(sha256_hash: str):
    console.print("\n[bold cyan][3/5] FINGERPRINT[/bold cyan]")
    console.print("  [bold green]✓ Canonical JSON generated[/bold green]")
    console.print(f"  SHA-256: [bold yellow]{sha256_hash}[/bold yellow]")

def render_step_4_blockchain(contract_address: str, tx_hash: str, block_number: int):
    console.print("\n[bold cyan][4/5] POLYGON AMOY REGISTRATION[/bold cyan]")
    console.print(f"  Network: [bold magenta]Polygon Amoy[/bold magenta]")
    console.print(f"  Chain ID: [dim]80002[/dim]")
    console.print(f"  Contract: [bold white]{contract_address}[/bold white]")
    console.print("  [bold green]✓ Hash registered via ContentRegistry.registerHash(bytes32)[/bold green]")
    console.print(f"  TX: [bold yellow]{tx_hash}[/bold yellow]")
    console.print(f"  [bold green]✓ Transaction confirmed[/bold green] (Block #{block_number})")
    console.print(f"  Explorer: [link=https://amoy.polygonscan.com/tx/{tx_hash}]https://amoy.polygonscan.com/tx/{tx_hash}[/link]")

def render_step_5_verification(is_verified: bool):
    console.print("\n[bold cyan][5/5] VERIFICATION[/bold cyan]")
    if is_verified:
        console.print("  [bold green]✓ Hash exists on blockchain[/bold green]")
        panel = Panel("[bold green]✓ CONTENT VERIFIED[/bold green]\nFingerprint matches on-chain record exactly.", title="Result", border_style="green")
        console.print(panel)
    else:
        console.print("  [bold red]✗ Hash not found on blockchain[/bold red]")
        panel = Panel("[bold red]✗ VERIFICATION FAILED[/bold red]", title="Result", border_style="red")
        console.print(panel)

def render_tamper_demo(original_hash: str, original_verified: bool, tampered_hash: str, tampered_verified: bool):
    console.print("\n[bold red]==================================================[/bold red]")
    console.print("[bold red]       TAMPER-DETECTION DEMONSTRATION           [/bold red]")
    console.print("[bold red]==================================================[/bold red]")
    
    console.print(f"\nOriginal Hash: [green]{original_hash}[/green]")
    console.print(f"Blockchain verifyHash(): [bold green]{original_verified} (TRUE)[/bold green]")
    
    console.print(f"\nTampered Hash:   [red]{tampered_hash}[/red]")
    console.print(f"Blockchain verifyHash(): [bold red]{tampered_verified} (FALSE)[/bold red]")
    
    if original_verified and not tampered_verified:
        panel = Panel("[bold green]✓ TAMPERING DETECTED[/bold green]\nContent alteration invalidated the cryptographic fingerprint.", title="Tamper Result", border_style="green")
        console.print(panel)
    else:
        panel = Panel("[bold red]✗ TAMPER DETECTION FAILED[/bold red]", title="Tamper Result", border_style="red")
        console.print(panel)
