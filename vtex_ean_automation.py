import os
import asyncio
import pandas as pd
import aiohttp
import argparse
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

# Load environment variables
load_dotenv()

VTEX_ACCOUNT_NAME = os.getenv("VTEX_ACCOUNT_NAME")
VTEX_ENVIRONMENT = os.getenv("VTEX_ENVIRONMENT", "vtexcommercestable")
VTEX_APP_KEY = os.getenv("VTEX_APP_KEY")
VTEX_APP_TOKEN = os.getenv("VTEX_APP_TOKEN")

BASE_URL = f"https://{VTEX_ACCOUNT_NAME}.{VTEX_ENVIRONMENT}.com.br/api/catalog/pvt"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-VTEX-API-AppKey": VTEX_APP_KEY,
    "X-VTEX-API-AppToken": VTEX_APP_TOKEN
}

TIMEOUT = aiohttp.ClientTimeout(total=10)
console = Console()

async def check_sku_ean(session, sku_id):
    """Checks if a SKU already has EANs asynchronously."""
    url = f"{BASE_URL}/stockkeepingunit/{sku_id}/ean"
    try:
        async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as response:
            if response.status == 200:
                eans = await response.json()
                return eans if eans else []
            elif response.status == 404:
                return []
            else:
                text = await response.text()
                return None, f"Error {response.status}: {text}"
    except Exception as e:
        return None, str(e)

async def delete_sku_ean(session, sku_id, ean):
    """Deletes an existing EAN from a SKU asynchronously."""
    url = f"{BASE_URL}/stockkeepingunit/{sku_id}/ean/{ean}"
    try:
        async with session.delete(url, headers=HEADERS, timeout=TIMEOUT) as response:
            if response.status in [200, 204]:
                return True, "Deleted"
            else:
                text = await response.text()
                return False, f"{response.status} - {text}"
    except Exception as e:
        return False, str(e)

async def create_sku_ean(session, sku_id, ean):
    """Creates an EAN for a SKU asynchronously."""
    url = f"{BASE_URL}/stockkeepingunit/{sku_id}/ean/{ean}"
    try:
        async with session.post(url, headers=HEADERS, timeout=TIMEOUT) as response:
            if response.status in [200, 201]:
                return True, "Success"
            else:
                text = await response.text()
                return False, f"{response.status} - {text}"
    except Exception as e:
        return False, str(e)

async def process_row(session, semaphore, index, row, args, progress, task_id):
    """Processes a single row with rate limiting (semaphore) and error handling."""
    sku_id = ""
    ean = ""
    try:
        async with semaphore:
            sku_id = str(row['SKU']).strip()
            ean = str(row['ean']).strip()

            if not sku_id or sku_id == "nan" or sku_id == "None":
                error_msg = "Missing SKU ID"
                if progress: progress.update(task_id, advance=1, description=f"[yellow]Linha {index}: {error_msg}")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Skipped", "message": error_msg}

            if not ean or ean == "nan" or ean == "None":
                error_msg = "Missing EAN"
                if progress: progress.update(task_id, advance=1, description=f"[yellow]SKU {sku_id}: {error_msg}")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Skipped", "message": error_msg}

            if progress: progress.update(task_id, description=f"[cyan]Verificando SKU {sku_id}...")

            check_result = await check_sku_ean(session, sku_id)

            if isinstance(check_result, tuple):  # Error case
                if progress: progress.update(task_id, advance=1, description=f"[red]SKU {sku_id}: Erro na verificação")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Error", "message": check_result[1]}

            existing_eans = check_result

            # EAN já está correto e é o único, nada a fazer
            if existing_eans == [ean]:
                if progress: progress.update(task_id, advance=1, description=f"[blue]SKU {sku_id}: EAN já está atualizado")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Already Up-to-date", "message": f"EAN {ean} já está correto"}

            if args.dry_run:
                if existing_eans:
                    msg = f"Deletaria {len(existing_eans)} EAN(s) {existing_eans} → cadastraria {ean}"
                else:
                    msg = f"Criaria EAN {ean}"
                if progress: progress.update(task_id, advance=1, description=f"[magenta]SKU {sku_id}: Simulação")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Dry-Run", "message": msg}

            # Deleta TODOS os EANs existentes antes de cadastrar o novo
            if existing_eans:
                for old_ean in existing_eans:
                    if progress: progress.update(task_id, description=f"[yellow]Deletando EAN {old_ean} de {sku_id}...")
                    deleted, del_msg = await delete_sku_ean(session, sku_id, old_ean)
                    if not deleted:
                        if progress: progress.update(task_id, advance=1, description=f"[red]SKU {sku_id}: Falha ao deletar {old_ean}")
                        return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Error", "message": f"Falha ao deletar EAN {old_ean}: {del_msg}"}

            # Cadastra o novo EAN
            if progress: progress.update(task_id, description=f"[bold green]Cadastrando novo EAN para {sku_id}...")
            success, message = await create_sku_ean(session, sku_id, ean)
            if success:
                status = "Replaced" if existing_eans else "Created"
                label = "Substituído" if existing_eans else "Criado"
                if progress: progress.update(task_id, advance=1, description=f"[green]SKU {sku_id}: {label}!")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": status, "message": message}
            else:
                if progress: progress.update(task_id, advance=1, description=f"[red]SKU {sku_id}: Falha ao cadastrar")
                return {**row.to_dict(), "ID VTEX": sku_id, "ean": ean, "status": "Error", "message": message}

    except Exception as e:
        if progress: progress.update(task_id, advance=1, description=f"[bold red]SKU {sku_id}: Erro crítico")
        return {**row.to_dict(), "status": "Error", "message": f"Critical Error: {str(e)}"}

async def main():
    parser = argparse.ArgumentParser(description="VTEX SKU EAN Automation (Async & Stable)")
    parser.add_argument("--file", default="resultado_consulta_sku.xlsx", help="Caminho para o arquivo XLSX")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Executar sem fazer alterações")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run", help="Executar alterações reais")
    parser.add_argument("--concurrency", type=int, default=3, help="Número de requisições simultâneas")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold blue]VTEX SKU EAN Automation v2.0[/bold blue]\n"
        f"Modo: {'[bold magenta]Simulação (Dry-Run)[/]' if args.dry_run else '[bold red]Execução Real[/]'}\n"
        f"Arquivo: [cyan]{args.file}[/]\n"
        f"Concorrência: [green]{args.concurrency}[/]",
        title="Iniciando"
    ))

    if not all([VTEX_ACCOUNT_NAME, VTEX_APP_KEY, VTEX_APP_TOKEN]):
        console.print("[bold red]Erro:[/] Credenciais VTEX ausentes no arquivo .env.")
        return

    try:
        df = pd.read_excel(args.file, dtype=str)

        df['ID VTEX'] = (df['SKU'].astype(str)
                         .str.replace(r'\.0$', '', regex=True)
                         .replace('nan', '')
                         .str.strip()
                         .str.strip('"\''))

        df['ean'] = (df['ean'].astype(str)
                     .str.replace(r'\.0$', '', regex=True)
                     .replace('nan', '')
                     .str.strip()
                     .str.strip('"\''))
    except Exception as e:
        console.print(f"[bold red]Erro ao ler arquivo:[/] {str(e)}")
        return

    semaphore = asyncio.Semaphore(args.concurrency)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        auto_refresh=True
    ) as progress:

        main_task = progress.add_task("Processando SKUs...", total=len(df))

        connector = aiohttp.TCPConnector(limit=args.concurrency)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for index, row in df.iterrows():
                tasks.append(process_row(session, semaphore, index, row, args, progress, main_task))

            results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = [r for r in results if isinstance(r, dict)]
    errors = [str(r) for r in results if not isinstance(r, dict)]

    if errors:
        console.print(f"[bold red]Aviso:[/] Ocorreram {len(errors)} erros internos durante o processamento.")

    # Save report
    report_df = pd.DataFrame(processed_results)
    report_df['ean'] = report_df['ean'].astype(str)
    report_filename = "execution_report.xlsx"
    report_df.to_excel(report_filename, index=False)

    if not report_df.empty:
        summary = report_df['status'].value_counts().to_dict()
        table = Table(title="\nResumo da Execução")
        table.add_column("Status", style="cyan")
        table.add_column("Quantidade", style="magenta")
        for status, count in summary.items():
            table.add_row(status, str(count))
        console.print(table)

    console.print(f"\n[bold green]Finalizado![/] Relatório salvo em: [bold]{report_filename}[/]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrompido pelo usuário.[/]")
