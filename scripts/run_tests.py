#!/usr/bin/env python3
"""
Script para executar testes e gerar relatório de cobertura

Este script executa todos os testes do sistema e gera um relatório de cobertura
detalhado em formato HTML e XML.
"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def run_tests():
    """
    Executa os testes e gera relatório de cobertura
    
    Returns:
        bool: True se todos os testes passaram
    """
    print("🧪 Executando testes com cobertura...")
    
    # Obter diretório raiz do projeto
    root_dir = Path(__file__).parent.parent.absolute()
    
    # Comando para executar testes com cobertura
    cmd = [
        "python", "-m", "pytest",
        "--cov=src",
        "--cov-report=term",
        "--cov-report=html:coverage_html_report",
        "--cov-report=xml:coverage.xml",
        "-v"
    ]
    
    # Executar comando
    result = subprocess.run(cmd, cwd=root_dir)
    
    # Verificar resultado
    if result.returncode == 0:
        print("✅ Todos os testes passaram!")
        return True
    else:
        print("❌ Alguns testes falharam!")
        return False

def show_coverage_report():
    """
    Abre o relatório de cobertura no navegador
    """
    # Obter diretório raiz do projeto
    root_dir = Path(__file__).parent.parent.absolute()
    
    # Caminho para o relatório HTML
    report_path = root_dir / "coverage_html_report" / "index.html"
    
    if report_path.exists():
        print(f"📊 Abrindo relatório de cobertura: {report_path}")
        
        # Tentar abrir no navegador
        try:
            webbrowser.open(f"file://{report_path}")
        except Exception as e:
            print(f"⚠️ Não foi possível abrir o navegador: {e}")
            print(f"📂 Abra manualmente o arquivo: {report_path}")
    else:
        print("⚠️ Relatório de cobertura não encontrado!")

def print_coverage_summary():
    """
    Imprime resumo da cobertura
    """
    # Obter diretório raiz do projeto
    root_dir = Path(__file__).parent.parent.absolute()
    
    # Caminho para o relatório XML
    report_path = root_dir / "coverage.xml"
    
    if report_path.exists():
        print("\n📊 Resumo da cobertura:")
        
        # Executar comando para mostrar resumo
        cmd = ["python", "-m", "coverage", "report"]
        subprocess.run(cmd, cwd=root_dir)
    else:
        print("⚠️ Relatório de cobertura XML não encontrado!")

def main():
    """
    Função principal
    """
    print("🚀 Iniciando execução de testes e geração de relatório de cobertura...")
    
    # Executar testes
    tests_passed = run_tests()
    
    # Imprimir resumo da cobertura
    print_coverage_summary()
    
    # Mostrar relatório de cobertura
    show_coverage_report()
    
    # Retornar código de saída
    return 0 if tests_passed else 1

if __name__ == "__main__":
    sys.exit(main())

