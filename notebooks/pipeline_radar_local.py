"""
╔══════════════════════════════════════════════════════════════╗
║         PIPELINE RADAR LOCAL CG — 4 AGENTES EM SEQUÊNCIA    ║
║  Agente 1: Coleta → Agente 2: Qualifica → Agente 3: Planeja ║
║  → Agente 4: Gera Pitch → Exporta XLSX pronto para disparar ║
╚══════════════════════════════════════════════════════════════╝

Instalação:
    pip install requests pandas openpyxl anthropic

Configuração:
    1. Preencha GOOGLE_MAPS_API_KEY  → console.cloud.google.com (Places API)
    2. Preencha ANTHROPIC_API_KEY    → console.anthropic.com
    3. (Opcional) Preencha MAILERFIND_API_KEY para e-mail de clientes dos seus prospects
    4. python pipeline_radar_local.py
"""

import requests
import pandas as pd
import re
import time
import json
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
import anthropic

# ═══════════════════════════════════════════════
# CONFIGURAÇÕES GLOBAIS
# ═══════════════════════════════════════════════
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "SUA_CHAVE_GOOGLE_MAPS")
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY",   "SUA_CHAVE_ANTHROPIC")

CIDADE = "Campina Grande, PB, Brasil"
NICHOS = [
    "clínica de estética",
    "salão de beleza",
    "clínica odontológica",
    "fisioterapia",
    "psicólogo",
    "academia",
    "barbearia",
]

NOTA_MAXIMA    = 4.2
MIN_AVALIACOES = 5
MAX_AVALIACOES = 300
MAX_POR_NICHO  = 10

MODEL = "claude-opus-4-5"

# ═══════════════════════════════════════════════
# ESTRUTURA DE DADOS DO PROSPECT
# ═══════════════════════════════════════════════
@dataclass
class Prospect:
    # Agente 1 — Coleta
    place_id:     str = ""
    nome:         str = ""
    endereco:     str = ""
    nota:         float = 0.0
    reviews:      int = 0
    nicho:        str = ""
    maps_url:     str = ""

    # Agente 2 — Qualificação
    telefone:     str = ""
    whatsapp:     str = ""
    site:         str = ""
    tem_site:     bool = False
    score:        int = 0
    problema:     str = ""
    prioridade:   str = ""  # ALTA / MÉDIA / BAIXA

    # Agente 3 — Planejamento
    servico_ideal:      str = ""
    preco_setup:        int = 0
    preco_mensalidade:  int = 0
    argumento_chave:    str = ""

    # Agente 4 — Pitch
    mensagem_whatsapp: str = ""
    link_whatsapp:     str = ""
    assunto_email:     str = ""
    corpo_email:       str = ""

    # Controle
    status:      str = "novo"
    data_coleta: str = ""


# ═══════════════════════════════════════════════
# AGENTE 1 — COLETA (Google Maps Places API)
# ═══════════════════════════════════════════════
class AgenteColeta:
    """
    Busca negócios locais no Google Maps, filtra por critérios
    de qualificação e retorna lista de Prospects básicos.
    Fonte: dados públicos voluntariamente cadastrados pelos donos.
    """

    def buscar(self, nicho: str) -> list[Prospect]:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": f"{nicho} em {CIDADE}",
            "language": "pt-BR",
            "key": GOOGLE_MAPS_API_KEY,
        }
        prospects = []
        while True:
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            for p in data.get("results", []):
                nota    = p.get("rating", 0)
                reviews = p.get("user_ratings_total", 0)
                if not (nota <= NOTA_MAXIMA and MIN_AVALIACOES <= reviews <= MAX_AVALIACOES):
                    continue
                prospects.append(Prospect(
                    place_id   = p.get("place_id", ""),
                    nome       = p.get("name", ""),
                    endereco   = p.get("formatted_address", ""),
                    nota       = nota,
                    reviews    = reviews,
                    nicho      = nicho,
                    data_coleta= datetime.now().strftime("%Y-%m-%d"),
                ))
            token = data.get("next_page_token")
            if not token:
                break
            time.sleep(2)
            params = {"pagetoken": token, "key": GOOGLE_MAPS_API_KEY}
        return prospects[:MAX_POR_NICHO]

    def enriquecer(self, p: Prospect) -> Prospect:
        """Busca detalhes: telefone, site, URL do Maps."""
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": p.place_id,
            "fields": "formatted_phone_number,international_phone_number,website,url",
            "language": "pt-BR",
            "key": GOOGLE_MAPS_API_KEY,
        }
        r = requests.get(url, params=params, timeout=15)
        res = r.json().get("result", {})

        tel_br  = res.get("formatted_phone_number", "")
        tel_int = res.get("international_phone_number", "")
        p.site     = res.get("website", "")
        p.tem_site = bool(p.site)
        p.maps_url = res.get("url", "")
        p.telefone = tel_br

        # Detecta se é celular (WhatsApp)
        for t in [tel_br, tel_int]:
            digits = re.sub(r"\D", "", t)
            if len(digits) in (11, 13):
                pos = -9 if len(digits) == 11 else -9
                if digits[pos] == "9":
                    p.whatsapp = digits if len(digits) == 13 else "55" + digits
                    break
        return p

    def rodar(self) -> list[Prospect]:
        todos = []
        for nicho in NICHOS:
            print(f"\n[Agente 1] 🔍 Coletando: {nicho}...")
            prospects = self.buscar(nicho)
            for i, p in enumerate(prospects):
                p = self.enriquecer(p)
                print(f"  [{i+1}/{len(prospects)}] {p.nome} | nota {p.nota} | WA: {'✓' if p.whatsapp else '✗'} | site: {'✓' if p.tem_site else '✗'}")
                todos.append(p)
                time.sleep(0.4)
        print(f"\n[Agente 1] ✅ {len(todos)} prospects coletados")
        return todos


# ═══════════════════════════════════════════════
# AGENTE 2 — QUALIFICAÇÃO (scoring + problema)
# ═══════════════════════════════════════════════
class AgenteQualificacao:
    """
    Analisa cada prospect e atribui:
    - Score de 0 a 100 (quanto maior, maior a dor)
    - Problema principal identificado
    - Prioridade de abordagem (ALTA / MÉDIA / BAIXA)
    """

    def pontuar(self, p: Prospect) -> Prospect:
        score = 0
        problemas = []

        # Nota baixa = dor de reputação
        if p.nota < 3.5:
            score += 40
            problemas.append(f"nota crítica {p.nota} ⭐")
        elif p.nota < 4.0:
            score += 25
            problemas.append(f"nota baixa {p.nota} ⭐")
        elif p.nota <= 4.2:
            score += 10
            problemas.append(f"nota mediana {p.nota} ⭐")

        # Sem site = dor de presença digital
        if not p.tem_site:
            score += 30
            problemas.append("sem site profissional")

        # Poucos reviews = não gerencia reputação
        if p.reviews < 20:
            score += 20
            problemas.append(f"apenas {p.reviews} avaliações")
        elif p.reviews < 50:
            score += 10
            problemas.append(f"{p.reviews} avaliações (potencial não explorado)")

        # Tem WhatsApp = mais fácil de contatar
        if p.whatsapp:
            score += 10

        p.score    = min(score, 100)
        p.problema = " + ".join(problemas) if problemas else "presença digital fraca"
        p.prioridade = "ALTA" if score >= 60 else "MÉDIA" if score >= 35 else "BAIXA"
        return p

    def rodar(self, prospects: list[Prospect]) -> list[Prospect]:
        print(f"\n[Agente 2] 📊 Qualificando {len(prospects)} prospects...")
        qualificados = [self.pontuar(p) for p in prospects]
        qualificados.sort(key=lambda x: x.score, reverse=True)

        altas  = sum(1 for p in qualificados if p.prioridade == "ALTA")
        medias = sum(1 for p in qualificados if p.prioridade == "MÉDIA")
        baixas = sum(1 for p in qualificados if p.prioridade == "BAIXA")
        print(f"[Agente 2] ✅ ALTA: {altas} | MÉDIA: {medias} | BAIXA: {baixas}")
        return qualificados


# ═══════════════════════════════════════════════
# AGENTE 3 — PLANEJAMENTO (serviço + precificação)
# ═══════════════════════════════════════════════
class AgentePlanejamento:
    """
    Define qual serviço oferecer para cada prospect,
    quanto cobrar e qual é o argumento de fechamento.
    Baseado no modelo LeadForge+Claude: setup fixo + mensalidade.
    """

    TABELA = {
        "sem_site_nota_baixa": {
            "servico":      "Site profissional + gestão de reputação Google",
            "setup":        800,
            "mensalidade":  150,
            "argumento":    "2 clientes a mais por mês já pagam o serviço inteiro",
        },
        "sem_site":  {
            "servico":      "Site profissional com botão WhatsApp e SEO local",
            "setup":        600,
            "mensalidade":  120,
            "argumento":    "Clientes buscam no Google e não te encontram — isso custa clientes todo dia",
        },
        "nota_baixa": {
            "servico":      "Gestão de reputação: respostas automáticas a reviews + captação de avaliações",
            "setup":        400,
            "mensalidade":  200,
            "argumento":    "Nota abaixo de 4 afasta 40% dos clientes que chegariam por indicação",
        },
        "padrao": {
            "servico":      "Presença digital completa: site + Google Meu Negócio + WhatsApp automático",
            "setup":        500,
            "mensalidade":  130,
            "argumento":    "Automação de atendimento e captação passiva de leads 24h",
        },
    }

    def planejar(self, p: Prospect) -> Prospect:
        if not p.tem_site and p.nota < 4.0:
            chave = "sem_site_nota_baixa"
        elif not p.tem_site:
            chave = "sem_site"
        elif p.nota < 4.0:
            chave = "nota_baixa"
        else:
            chave = "padrao"

        t = self.TABELA[chave]
        p.servico_ideal     = t["servico"]
        p.preco_setup       = t["setup"]
        p.preco_mensalidade = t["mensalidade"]
        p.argumento_chave   = t["argumento"]
        return p

    def rodar(self, prospects: list[Prospect]) -> list[Prospect]:
        print(f"\n[Agente 3] 📋 Planejando proposta para {len(prospects)} prospects...")
        planejados = [self.planejar(p) for p in prospects]
        print(f"[Agente 3] ✅ Propostas definidas")
        return planejados


# ═══════════════════════════════════════════════
# AGENTE 4 — PITCH (mensagem WhatsApp + e-mail)
# ═══════════════════════════════════════════════
class AgentePitch:
    """
    Usa Claude para gerar mensagem de WhatsApp personalizada
    e assunto/corpo de e-mail para cada prospect qualificado.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    def gerar_whatsapp(self, p: Prospect) -> str:
        prompt = f"""Crie uma mensagem de WhatsApp curta e direta para abordar este negócio local:

Negócio: {p.nome} ({p.nicho})
Problema: {p.problema}
Serviço a oferecer: {p.servico_ideal}
Argumento principal: {p.argumento_chave}
Preço setup: R${p.preco_setup} | Mensalidade: R${p.preco_mensalidade}/mês

Regras:
- Máximo 5 linhas
- Tom consultivo, não de vendedor genérico
- Mencione o problema específico identificado (nota ou falta de site)
- Termine com UMA pergunta aberta simples
- Máximo 1 emoji
- NÃO diga "vi seu perfil" — diga "encontrei no Google"
- Assine: Radar Local CG

Retorne APENAS o texto da mensagem."""

        msg = self.client.messages.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()

    def gerar_email(self, p: Prospect) -> tuple[str, str]:
        prompt = f"""Crie um e-mail frio profissional para este prospect:

Negócio: {p.nome} ({p.nicho})
Problema: {p.problema}
Serviço: {p.servico_ideal}
Argumento: {p.argumento_chave}
Investimento: R${p.preco_setup} setup + R${p.preco_mensalidade}/mês

Formato de resposta (JSON):
{{
  "assunto": "assunto do e-mail em até 8 palavras",
  "corpo": "e-mail completo em até 150 palavras, tom consultivo, CTA claro no final"
}}

Retorne APENAS o JSON."""

        msg = self.client.messages.create(
            model=MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            data = json.loads(msg.content[0].text.strip())
            return data.get("assunto", ""), data.get("corpo", "")
        except Exception:
            return "Encontramos uma oportunidade para seu negócio", msg.content[0].text.strip()

    def rodar(self, prospects: list[Prospect]) -> list[Prospect]:
        com_contato = [p for p in prospects if p.whatsapp or p.site]
        sem_contato = [p for p in prospects if not p.whatsapp and not p.site]

        print(f"\n[Agente 4] ✍️  Gerando pitches para {len(com_contato)} prospects com contato...")

        for i, p in enumerate(com_contato):
            print(f"  [{i+1}/{len(com_contato)}] {p.nome}...")
            try:
                if p.whatsapp:
                    p.mensagem_whatsapp = self.gerar_whatsapp(p)
                    p.link_whatsapp = (
                        f"https://wa.me/{p.whatsapp}?text="
                        + requests.utils.quote(p.mensagem_whatsapp)
                    )
                p.assunto_email, p.corpo_email = self.gerar_email(p)
            except Exception as e:
                p.mensagem_whatsapp = f"[Erro: {e}]"
            time.sleep(0.5)

        for p in sem_contato:
            p.mensagem_whatsapp = "Sem WhatsApp — abordar pessoalmente ou via Instagram DM"
            p.status = "sem_contato"

        print(f"[Agente 4] ✅ Pitches gerados")
        return com_contato + sem_contato


# ═══════════════════════════════════════════════
# EXPORTAÇÃO — XLSX com abas organizadas
# ═══════════════════════════════════════════════
def exportar(prospects: list[Prospect]) -> str:
    df = pd.DataFrame([asdict(p) for p in prospects])

    # Aba principal — apenas o essencial para disparar
    colunas_disparo = [
        "prioridade", "score", "nome", "nicho", "nota", "reviews",
        "problema", "telefone", "whatsapp", "link_whatsapp",
        "servico_ideal", "preco_setup", "preco_mensalidade",
        "mensagem_whatsapp", "assunto_email", "status"
    ]
    df_disparo = df[[c for c in colunas_disparo if c in df.columns]]

    # Aba completa — todos os dados
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    nome = f"pipeline_radar_local_{ts}.xlsx"

    with pd.ExcelWriter(nome, engine="openpyxl") as writer:
        df_disparo.to_excel(writer, index=False, sheet_name="📋 Disparar Hoje")
        df.to_excel(writer, index=False, sheet_name="🗂 Dados Completos")

        # Formata largura das colunas
        for sheet in writer.sheets.values():
            for col in sheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                sheet.column_dimensions[col[0].column_letter].width = min(max_len + 3, 70)

    print(f"\n✅ Exportado: {nome}")
    return nome


# ═══════════════════════════════════════════════
# ORQUESTRADOR — executa os 4 agentes em sequência
# ═══════════════════════════════════════════════
def rodar_pipeline():
    print("=" * 60)
    print("  PIPELINE RADAR LOCAL CG — INICIANDO")
    print("=" * 60)

    # Agente 1 — Coleta
    prospects = AgenteColeta().rodar()

    # Agente 2 — Qualificação
    prospects = AgenteQualificacao().rodar(prospects)

    # Agente 3 — Planejamento
    prospects = AgentePlanejamento().rodar(prospects)

    # Agente 4 — Pitch
    prospects = AgentePitch().rodar(prospects)

    # Exporta
    arquivo = exportar(prospects)

    # Resumo final
    altas = [p for p in prospects if p.prioridade == "ALTA"]
    print("\n" + "=" * 60)
    print(f"  PIPELINE CONCLUÍDO")
    print(f"  Total prospects:    {len(prospects)}")
    print(f"  Prioridade ALTA:    {len(altas)}")
    print(f"  Com WhatsApp:       {sum(1 for p in prospects if p.whatsapp)}")
    print(f"  Com mensagem pronta:{sum(1 for p in prospects if p.mensagem_whatsapp and 'Erro' not in p.mensagem_whatsapp)}")
    print(f"  Arquivo gerado:     {arquivo}")
    print("=" * 60)

    # Top 5 para abordar hoje
    print("\n🎯 TOP 5 PARA ABORDAR HOJE:")
    for i, p in enumerate(altas[:5], 1):
        print(f"  {i}. {p.nome} | score {p.score} | {p.problema}")


if __name__ == "__main__":
    rodar_pipeline()
