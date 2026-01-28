import streamlit as st
import pandas as pd
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import re
from pdf2image import convert_from_bytes
from datetime import datetime, timedelta

# --- MOTORES DE PROCESSAMENTO ---
def preparar_imagem(img):
    img = ImageOps.grayscale(img)
    return ImageEnhance.Contrast(img).enhance(3.0)

def limpar_v(texto):
    if not texto: return 0.0
    # Captura valores no formato 1.234,56 ou 1234,56
    match = re.search(r'(\d{1,3}(\.\d{3})*,\d{2})', texto)
    if match:
        return float(match.group(1).replace('.', '').replace(',', '.'))
    return 0.0

def gerenciar_data(texto, meses_limite, modo="emissao"):
    datas = re.findall(r'(\d{2}/\d{2}/\d{4})', texto)
    if not datas: return "✅ IMPORTADO"
    
    agora = datetime.now()
    try:
        objetos_data = [datetime.strptime(d, '%d/%m/%Y') for d in datas]
        # Para residência/extrato usamos a emissão (mais recente), para renda a competência
        data_doc = max(objetos_data) if modo == "emissao" else min(objetos_data)
        
        limite = agora - timedelta(days=meses_limite * 30)
        if data_doc < limite:
            return "⚠️ DOCUMENTO EXPIRADO"
        return "✅ DOCUMENTO VÁLIDO"
    except:
        return "✅ IMPORTADO"

# --- MOTOR DE EXTRAÇÃO (LÓGICA DO PROMPT) ---
def motor_analise_caixa_v7(dados_consolidados):
    t = dados_consolidados.upper()
    res = {}

    # Extração de Identificação
    res['nome'] = next((n.strip() for n in re.findall(r'(?:NOME|CLIENTE)[:\s]+([A-Z\s]{12,})', t) if "NEO" not in n), "Não detectado")
    res['cpf'] = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t).group(1) if re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', t) else "Não detectado"
    res['rg'] = re.search(r'(?:RG|IDENTIDADE)[:\s]*([\d\.X-]{7,12})', t).group(1) if re.search(r'(?:RG|IDENTIDADE)[:\s]*([\d\.X-]{7,12})', t) else "Não detectado"
    res['nasc'] = re.search(r'(?:NASCIMENTO|NASC)[:\s]*(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(?:NASCIMENTO|NASC)[:\s]*(\d{2}/\d{2}/\d{4})', t) else "Não detectado"
    res['estado_civil'] = re.search(r'(?:ESTADO CIVIL)[:\s]*([A-Z]+)', t).group(1) if re.search(r'(?:ESTADO CIVIL)[:\s]*([A-Z]+)', t) else "Não detectado"
    res['data_casamento'] = re.search(r'(?:CASAMENTO)[:\s]*(\d{2}/\d{2}/\d{4})', t).group(1) if re.search(r'(?:CASAMENTO)[:\s]*(\d{2}/\d{2}/\d{4})', t) else "N/A"
    
    # Endereço
    linhas = t.split('\n')
    res['endereco'] = next((l.strip() for l in linhas if "RUA" in l or "AV." in l or "ESTRADA" in l), "Não detectado")

    # Análise de Renda (Regra de Reincorporação)
    vencimentos = [limpar_v(v) for v in re.findall(r'(?:VENCIMENTOS|TOTAL PROVENTOS|BRUTO).*?([\d\.,]{6,})', t)]
    liquidos_brutos = [limpar_v(v) for v in re.findall(r'(?:TOTAL LIQUIDO|LIQUIDO PGTO).*?([\d\.,]{6,})', t)]
    # Busca por Adiantamentos nos descontos
    adiantamentos = [limpar_v(v) for v in re.findall(r'(?:ADIANTAMENTO|ANTECIPACAO|VALE|ADTO).*?([\d\.,]{5,})', t)]
    
    res['ultimo_bruto'] = vencimentos[-1] if vencimentos else 0.0
    res['media_bruta'] = sum(vencimentos)/len(vencimentos) if vencimentos else 0.0
    
    # Cálculo Líquido Real (Líquido + Adiantamento)
    ult_liq_puro = liquidos_brutos[-1] if liquidos_brutos else 0.0
    ult_adt = adiantamentos[-1] if adiantamentos else 0.0
    res['ultimo_liq_real'] = ult_liq_puro + ult_adt
    res['media_liq_real'] = (sum(liquidos_brutos) + sum(adiantamentos)) / len(liquidos_brutos) if liquidos_brutos else 0.0

    res['cargo'] = re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t).group(1).split('\n')[0].strip() if re.search(r'(?:CARGO|FUNCAO)[:\s]+([A-Z\s/]{5,})', t) else "Não detectado"
    
    # FGTS - Múltiplas Empresas
    empresas = re.findall(r'(?:EMPRESA|EMPREGADOR)[:\s]+([A-Z\s\.]{10,})', t)
    cnpjs = re.findall(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})', t)
    fins_rescisorios = re.findall(r'(?:FINS\s+RE[SC]{1,2}ISORIOS).*?([\d\.,]{5,})', t)
    creditos_de = re.findall(r'(?:CREDITO\s+DE).*?([\d\.,]{5,})', t)
    
    res['fgts_contas'] = []
    for i in range(len(fins_rescisorios)):
        nome_emp = empresas[i].strip() if i < len(empresas) else "Conta FGTS"
        res['fgts_contas'].append({
            "id": i+1,
            "empresa": nome_emp,
            "cnpj": cnpjs[i] if i < len(cnpjs) else "Contas Distintas",
            "fins": limpar_v(fins_rescisorios[i]),
            "credito": limpar_v(creditos_de[i]) if i < len(creditos_de) else 0.0
        })
    res['fgts_total'] = sum([c['fins'] + c['credito'] for c in res['fgts_contas']])

    return res

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Caixa Correspondente 2.0", layout="wide")

tab_geral, tab_import, tab_result = st.tabs(["Aba Geral", "Importação de Documentos", "Resultado das Análises"])

with tab_geral:
    st.header("Origem de Recursos")
    origem_selecionada = st.radio("Sinalizar origem de recursos:", 
                                  ["CLT", "Autônomos e Profissionais Liberais", "Empresários/MEI"])

with tab_import:
    st.header("Ler PDF e Imagens")
    st.subheader("Categorizar documentos para importação")
    
    status_importacao = []
    texto_total = ""

    col1, col2 = st.columns(2)
    with col1:
        u_id = st.file_uploader("Identificação (RG, CPF, CNH, Certidões)", accept_multiple_files=True)
        u_res = st.file_uploader("Comprovante de Residência", accept_multiple_files=True)
        u_extratos = st.file_uploader("Extratos Bancários (Últimos 6 meses)", accept_multiple_files=True)
    with col2:
        u_renda = st.file_uploader("Comprovação de Renda (Holerites)", accept_multiple_files=True)
        u_fgts = st.file_uploader("Extratos FGTS", accept_multiple_files=True)
        u_ir = st.file_uploader("IR / DECORE", accept_multiple_files=True)

    # Função interna para processar e validar datas por categoria
    def processar_arquivos(lista, tipo):
        global texto_total
        for f in lista:
            # OCR
            if f.type == "application/pdf":
                pags = convert_from_bytes(f.read(), 150)
                txt = " ".join([pytesseract.image_to_string(preparar_imagem(p), lang='por') for p in pags])
            else:
                txt = pytesseract.image_to_string(preparar_imagem(Image.open(f)), lang='por')
            
            # Gestão de Datas conforme o tipo
            if tipo == "identidade": status = "✅ IMPORTADO"
            elif tipo == "residencia": status = gerenciar_data(txt, 3) # 90 dias
            elif tipo == "renda": status = gerenciar_data(txt, 3, "competencia") # 3 meses
            elif tipo == "extratos": status = gerenciar_data(txt, 6) # 6 meses
            elif tipo == "ir": status = gerenciar_data(txt, 12) # 1 ano
            else: status = "✅ IMPORTADO"
            
            status_importacao.append({"Documento": f.name, "Status": status})
            texto_total += txt + " "

    if u_id: processar_arquivos(u_id, "identidade")
    if u_res: processar_arquivos(u_res, "residencia")
    if u_renda: processar_arquivos(u_renda, "renda")
    if u_extratos: processar_arquivos(u_extratos, "extratos")
    if u_fgts: processar_arquivos(u_fgts, "fgts")
    if u_ir: processar_arquivos(u_ir, "ir")

    if status_importacao:
        st.table(pd.DataFrame(status_importacao))
        analise_final = motor_analise_caixa_v7(texto_total)

with tab_result:
    if 'analise_final' in locals():
        st.header("Relatório Final de Análise")
        
        # Extrair Dados
        with st.expander("👤 Dados Pessoais e Identificação", expanded=True):
            col_a, col_b = st.columns(2)
            col_a.write(f"**Nome:** {analise_final['nome']}")
            col_a.write(f"**CPF:** {analise_final['cpf']}")
            col_a.write(f"**RG:** {analise_final['rg']}")
            col_a.write(f"**Nascimento:** {analise_final['nasc']}")
            col_b.write(f"**Origem:** {origem_selecionada}")
            col_b.write(f"**Estado Civil:** {analise_final['estado_civil']}")
            col_b.write(f"**Data Casamento:** {analise_final['data_casamento']}")
            col_b.write(f"**Endereço:** {analise_final['endereco']}")

        # Extrair Renda
        with st.expander("💰 Detalhamento de Renda (Holerite)", expanded=True):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Cargo:** {analise_final['cargo']}")
            c1.info("Tempo de Casa: Admissão não detectada")
            c2.metric("Média Bruta", f"R$ {analise_final['media_bruta']:,.2f}")
            c2.metric("Média Líquida", f"R$ {analise_final['media_liq_real']:,.2f}")
            c3.metric("Último Bruto", f"R$ {analise_final['ultimo_bruto']:,.2f}")
            c3.metric("Último Líquido Real", f"R$ {analise_final['ultimo_liq_real']:,.2f}", delta="C/ Adiantamento")

        # Extrair FGTS
        with st.expander("📈 Detalhamento de FGTS", expanded=True):
            for conta in analise_final['fgts_contas']:
                st.write(f"**Conta {conta['id']}:** {conta['empresa']} | CNPJ: {conta['cnpj']}")
                st.write(f"Fins Rescisórios: R$ {conta['fins']:,.2f} | Crédito: R$ {conta['credito']:,.2f}")
                st.divider()
            st.success(f"**Saldo Total para Entrada:** R$ {analise_final['fgts_total']:,.2f}")

        # Veredito
        st.subheader("🏁 Veredito")
        enquadramento = "SBPE" if analise_final['ultimo_bruto'] > 8000 else "MCMV"
        status_aprov = "✅ ALTA" if analise_final['ultimo_bruto'] > 0 else "❌ DADOS INSUFICIENTES"
        
        v1, v2, v3 = st.columns(3)
        v1.write(f"**Modalidade:** {enquadramento}")
        v2.write(f"**Subsídio Estimado:** {'R$ 55.000,00' if enquadramento == 'MCMV' else 'R$ 0,00'}")
        v3.write(f"**Status:** {status_aprov}")

        if enquadramento == "SBPE" and analise_final['fgts_total'] < 20000:
            st.warning("⚠️ Necessidade de Complementação de Recursos (Saldo FGTS baixo para entrada SBPE).")
            
        st.button("🖨️ Imprimir Relatório Completo")
