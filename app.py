from datetime import datetime
import math
import re
import pandas as pd
import streamlit as st
import requests

st.set_page_config(page_title="Controle de Produção - Corte", layout="wide")

# Configurações do Supabase
SUPABASE_URL = "https://vswyzdimidmqsvawaswr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZzd3l6ZGltaWRtcXN2YXdhc3dyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5NzU1MjksImV4cCI6MjEwNjU1MTUyOX0.ZqUKsLBHiRL-ohz0uRl0G86KY_Y8dVzNwM9XPI01YGA"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# Nome exato da sua tabela no Supabase
TABLE_NAME = "Producao"


@st.cache_data(ttl=2)
def carregar_dados():
    """Lê os dados do Supabase e garante o padrão 'ID' para o resto do app."""
    try:
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=*"
        response = requests.get(url, headers=HEADERS)
        
        colunas_esperadas = ["ID", "Data", "Tipo", "Carga", "Codigo", "Perfis", "Sobras", "Status", "Policorte", "Agrupado"]

        if response.status_code == 200:
            data = response.json()
            if data:
                df = pd.DataFrame(data)
                
                # Se o Supabase retornar "id" em minúsculo, renomeia para "ID"
                if "id" in df.columns and "ID" not in df.columns:
                    df = df.rename(columns={"id": "ID"})

                # Garante que todas as colunas esperadas existam
                for col in colunas_esperadas:
                    if col not in df.columns:
                        df[col] = ""

                return df[colunas_esperadas]
            
            return pd.DataFrame(columns=colunas_esperadas)
        else:
            st.error(f"Erro ao carregar do Supabase: {response.status_code} - {response.text}")
            return pd.DataFrame(columns=colunas_esperadas)
    except Exception as e:
        st.error(f"Erro de conexão com o Supabase: {e}")
        return pd.DataFrame(columns=colunas_esperadas)

def salvar_dados(df):
    try:
        st.cache_data.clear()
        
        # 1. Copia o DataFrame
        df_envio = df.copy()

        # 2. Garante que a chave primária se chame "id" (minúsculo)
        if "ID" in df_envio.columns:
            df_envio = df_envio.rename(columns={"ID": "id"})

        # 3. Trata valores nulos / NaN para compatibilidade com JSON
        df_envio = df_envio.fillna("")
        for col in df_envio.columns:
            df_envio[col] = df_envio[col].astype(str).replace("nan", "")

        # 4. Converte para lista de dicionários
        records = df_envio.to_dict(orient="records")
        
        if not records:
            return

        # 5. Envia especificando 'on_conflict=id' no cabeçalho da requisição
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?on_conflict=id"
        headers_upsert = HEADERS.copy()
        headers_upsert["Prefer"] = "resolution=merge-duplicates"
        
        response = requests.post(url, headers=headers_upsert, json=records)
        
        if response.status_code in [200, 201]:
            st.toast("Dados salvos no Supabase com sucesso!", icon="⚡")
        else:
            st.error(f"Erro ao gravar no Supabase: {response.status_code} - {response.text}")
    except Exception as e:
        st.error(f"Erro ao salvar dados no Supabase: {e}")







def excluir_ordens_por_ids(lista_ids):
    """Exclui diretamente do Supabase os IDs passados em uma única requisição."""
    try:
        st.cache_data.clear()
        # Converte a lista de IDs para o formato do PostgREST: (id1,id2,id3)
        ids_str = ",".join(map(str, lista_ids))
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?id=in.({ids_str})"
        
        response = requests.delete(url, headers=HEADERS)
        
        if response.status_code in [200, 204]:
            return True
        else:
            st.error(f"Erro ao excluir do Supabase: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase para excluir: {e}")
        return False











def eh_perfil(nome):
    nome_upper = str(nome).strip().upper()
    baguetes = ["BB01B", "BJ05", "BJ03", "BJ06L"]
    if nome_upper.startswith("ES") or nome_upper in baguetes:
        return True
    return False

def criar_paginacao(total_itens, itens_por_pagina, chave_prefixo):
    """Função auxiliar para criar os botões de paginação compactos"""
    if total_itens <= itens_por_pagina:
        return 0, total_itens, 1, 1
    
    total_paginas = math.ceil(total_itens / itens_por_pagina)
    
    cols = st.columns([1] + [0.3] * min(total_paginas, 15) + [1])
    
    if f"pagina_{chave_prefixo}" not in st.session_state:
        st.session_state[f"pagina_{chave_prefixo}"] = 1
    
    pagina_atual = st.session_state[f"pagina_{chave_prefixo}"]
    if pagina_atual > total_paginas:
        pagina_atual = total_paginas
        st.session_state[f"pagina_{chave_prefixo}"] = total_paginas

    with cols[0]:
        if st.button("⬅️", key=f"ant_{chave_prefixo}", disabled=(pagina_atual == 1)):
            st.session_state[f"pagina_{chave_prefixo}"] -= 1
            st.rerun()

    inicio_loop = max(1, pagina_atual - 3)
    fim_loop = min(total_paginas, inicio_loop + 6)
    
    for p in range(inicio_loop, fim_loop + 1):
        idx_col = (p - inicio_loop) + 1
        if idx_col < len(cols) - 1:
            with cols[idx_col]:
                tipo_botao = "primary" if p == pagina_atual else "secondary"
                if st.button(str(p), key=f"p_{chave_prefixo}_{p}", type=tipo_botao):
                    st.session_state[f"pagina_{chave_prefixo}"] = p
                    st.rerun()

    with cols[-1]:
        if st.button("➡️", key=f"prox_{chave_prefixo}", disabled=(pagina_atual == total_paginas)):
            st.session_state[f"pagina_{chave_prefixo}"] += 1
            st.rerun()

    inicio = (pagina_atual - 1) * itens_por_pagina
    fim = min(inicio + itens_por_pagina, total_itens)
    return inicio, fim, pagina_atual, total_paginas

def aplicar_filtros_e_ordenacao(df, prefixo):
    """Componente avançado de filtros, busca, ordenação e agrupamento por código"""
    if df.empty:
        return df

    with st.expander("🔍 Filtros Avançados e Ordenação", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            f_codigo = st.text_input("Código", key=f"f_cod_{prefixo}")
        with col2:
            f_carga = st.text_input("Carga", key=f"f_car_{prefixo}")
        with col3:
            f_perfil = st.text_input("Perfil", key=f"f_per_{prefixo}")
        with col4:
            f_sobra = st.text_input("Sobra", key=f"f_sob_{prefixo}")
        with col5:
            f_data_obj = st.date_input("Data", value=None, key=f"f_dat_{prefixo}")

        st.markdown("---")
        col_ord1, col_ord2 = st.columns(2)
        with col_ord1:
            tipo_ordem = st.selectbox(
                "Ordenar por Código:",
                ["Padrão (ID)", "Menor para Maior (Crescente)", "Maior para Menor (Decrescente)"],
                key=f"ord_tipo_{prefixo}"
            )
        with col_ord2:
            agrupar_repetidas = st.checkbox(
                "Juntar ordens com o mesmo código juntas (Ignorar Data/Carga)",
                key=f"chk_agrupar_repetidas_{prefixo}"
            )

    df_filtrado = df.copy()

    if f_codigo:
        df_filtrado = df_filtrado[df_filtrado["Codigo"].astype(str).str.contains(f_codigo, case=False, na=False)]
    if f_carga:
        df_filtrado = df_filtrado[df_filtrado["Carga"].astype(str).str.contains(f_carga, case=False, na=False)]
    if f_perfil:
        df_filtrado = df_filtrado[df_filtrado["Perfis"].astype(str).str.contains(f_perfil, case=False, na=False)]
    if f_sobra:
        df_filtrado = df_filtrado[df_filtrado["Sobras"].astype(str).str.contains(f_sobra, case=False, na=False)]
    if f_data_obj:
        data_str = f_data_obj.strftime("%d/%m/%Y")
        df_filtrado = df_filtrado[df_filtrado["Data"].astype(str).str.contains(data_str, na=False)]

    if agrupar_repetidas:
        df_filtrado = df_filtrado.sort_values(by="Codigo", ascending=True)
    elif tipo_ordem == "Menor para Maior (Crescente)":
        df_filtrado = df_filtrado.sort_values(by="Codigo", ascending=True)
    elif tipo_ordem == "Maior para Menor (Decrescente)":
        df_filtrado = df_filtrado.sort_values(by="Codigo", ascending=False)

    return df_filtrado

def parse_string_itens(texto_str):
    resultado = {}
    if not isinstance(texto_str, str) or not texto_str.strip() or texto_str.strip() in ["Nenhum", "Nenhuma"]:
        return resultado
    
    partes = texto_str.split("|")
    for parte in partes:
        parte = parte.strip()
        # Busca o nome do item e todas as quantidades no formato (Qtd: X) ou (Qtd: X,XX)
        match = re.search(r'^(.*?)\s*\((?:Qtd:\s*[\d\.,]+)\)+', parte)
        if match:
            item_nome = match.group(1).strip()
            # Extrai todas as ocorrências de números de quantidade na string
            qtds = re.findall(r'Qtd:\s*([\d\.,]+)', parte)
            for q_str in qtds:
                try:
                    q_num = int(float(q_str.replace(",", ".")))
                    resultado[item_nome] = resultado.get(item_nome, 0) + q_num
                except:
                    pass
        elif parte:
            resultado[parte] = resultado.get(parte, 0) + 1
    return resultado
def formatar_string_itens(dicionario_itens, tipo_padrao):
    if not dicionario_itens:
        return "Nenhum" if tipo_padrao == "Perfil" else "Nenhuma"
    lista_formatada = [f"{nome} (Qtd: {qtd})" for nome, qtd in dicionario_itens.items()]
    return " | ".join(lista_formatada)

# --- CSS GLOBAL PARA COMPACTAR ESPAÇAMENTOS ---
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 1rem !important;
        }
        h3, h4, h5 {
            margin-bottom: 2px !important;
            margin-top: 2px !important;
        }
        hr {
            margin: 8px 0px !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# --- TÍTULO PRINCIPAL ---
st.markdown(
    "<h3 style='margin-bottom: 0px; padding-bottom: 0px;'>Controle de Produção - Corte</h3>",
    unsafe_allow_html=True,
)

# --- ABAS MODERNAS NO TOPO ---
aba1, aba2, aba3, aba4, aba5, aba6, aba7 = st.tabs(
    ["Ordens", "Separação", "Policorte 1", "Policorte 2", "Policorte 3", "Finalizadas", "📊 Análise de Cargas"]
)

# ==========================================
# ABA 1: ORDENS
# ==========================================
with aba1:
    st.markdown("<h4 style='margin-top: 2px;'>Cadastro de Ordens e Cargas</h4>", unsafe_allow_html=True)

    with st.form("form_ordem", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            txt_ordens = st.text_area(
                "Cole as Linhas (Ex: B219-248   B219-561   20)",
                height=100,
                placeholder="Cole aqui as linhas copiadas do seu sistema..."
            )
        with col2:
            txt_cargas = st.text_input("Número da Carga")

        tipo_selecionado = st.radio(
            "Tipo de Item:", ["Ordens Criadas", "Carga"], horizontal=True
        )

        submitted = st.form_submit_button("Salvar Ordens")

        if submitted:
            if not txt_ordens.strip():
                st.error("O campo de ordens não pode estar vazio!")
            else:
                with st.spinner("Processando e salvando ordens..."):
                    linhas = txt_ordens.strip().split("\n")
                    dados_temporarios = []

                    for linha in linhas:
                        partes = linha.strip().split()
                        if len(partes) >= 3:
                            codigo = partes[0]
                            item_secundario = partes[1]
                            qtd = partes[2]
                            tipo_item = "Perfil" if eh_perfil(item_secundario) else "Sobra"
                            dados_temporarios.append({
                                "Codigo": codigo, 
                                "Item": item_secundario, 
                                "Qtd": qtd, 
                                "TipoItem": tipo_item
                            })

                    if dados_temporarios:
                        df_temp = pd.DataFrame(dados_temporarios)
                        data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")
                        
                        df_atualizado = carregar_dados()

                        if df_atualizado.empty or "ID" not in df_atualizado.columns:
                            proximo_id = 1
                        else:
                            try:
                                df_atualizado["ID_num"] = pd.to_numeric(df_atualizado["ID"], errors="coerce")
                                max_id = df_atualizado["ID_num"].max()
                                proximo_id = int(max_id + 1) if pd.notna(max_id) else 1
                                df_atualizado = df_atualizado.drop(columns=["ID_num"])
                            except:
                                proximo_id = len(df_atualizado) + 1

                        novas_linhas = []
                        for codigo, grupo in df_temp.groupby("Codigo", sort=False):
                            perfis_lista = []
                            sobras_lista = []

                            for _, row in grupo.iterrows():
                                texto_item = f"{row['Item']} (Qtd: {row['Qtd']})"
                                if row['TipoItem'] == "Perfil":
                                    perfis_lista.append(texto_item)
                                else:
                                    sobras_lista.append(texto_item)

                            texto_perfis = " | ".join(perfis_lista) if perfis_lista else "Nenhum"
                            texto_sobras = " | ".join(sobras_lista) if sobras_lista else "Nenhuma"

                            novas_linhas.append({
                                "ID": str(proximo_id),
                                "Data": data_atual,
                                "Carga": str(txt_cargas).strip(),
                                "Codigo": str(codigo).strip(),
                                "Perfis": str(texto_perfis),
                                "Sobras": str(texto_sobras),
                                "Tipo": str(tipo_selecionado),
                                "Status": "Pendente",
                                "Policorte": "Nenhuma",
                                "Agrupado": "Não",
                            })
                            proximo_id += 1

                        if novas_linhas:
                            df_novas = pd.DataFrame(novas_linhas)
                            df_atualizado = pd.concat([df_atualizado, df_novas], ignore_index=True)
                            salvar_dados(df_atualizado)
                            st.success(f"Ordem salva com sucesso! {len(novas_linhas)} ordem(ns) processada(s).")
                    else:
                        st.error("Formato inválido. Certifique-se de colar no formato correto.")

    st.markdown("##### Ordens Cadastradas")
    df_global_atual = carregar_dados()
    if not df_global_atual.empty:
        df_global_atual["ID_num"] = pd.to_numeric(df_global_atual["ID"], errors="coerce")
        df_global_atual = df_global_atual.sort_values("ID_num", ascending=True).drop(columns=["ID_num"])
        
        df_global_atual = aplicar_filtros_e_ordenacao(df_global_atual, "cadastradas")

        total_cadastradas = len(df_global_atual)
        if total_cadastradas > 0:
            inicio_ord, fim_ord, pagina_atual_cad, total_pag_cad = criar_paginacao(total_cadastradas, 30, "cadastradas")
            df_cadastradas_pagina = df_global_atual.iloc[inicio_ord:fim_ord]

            # Mapeia contagem de códigos repetidos em todo o banco de dados
            contagem_codigos = df_global_atual["Codigo"].astype(str).str.strip().value_counts().to_dict()

            col_ctrl_ord1, col_ctrl_ord2, col_ctrl_ord3 = st.columns([1.5, 1.2, 1.2])
            with col_ctrl_ord1:
                def atualizar_todos_checkboxes_cad():
                    estado_desejado = st.session_state.get(f"master_chk_cad_{pagina_atual_cad}", False)
                    for _, r in df_cadastradas_pagina.iterrows():
                        st.session_state[f"chk_cad_{int(r['ID'])}"] = estado_desejado

                st.checkbox(
                    "Marcar/Desmarcar Todos da Página", 
                    key=f"master_chk_cad_{pagina_atual_cad}",
                    on_change=atualizar_todos_checkboxes_cad
                )

            with col_ctrl_ord2:
                if st.button("🚨 Priorizar Ordem", type="secondary", use_container_width=True):
                    ids_para_priorizar = []
                    for _, row in df_cadastradas_pagina.iterrows():
                        cid = int(row["ID"])
                        if st.session_state.get(f"chk_cad_{cid}", False):
                            ids_para_priorizar.append(cid)

                    if not ids_para_priorizar:
                        st.warning("Nenhuma ordem foi selecionada para priorizar!")
                    else:
                        df_atual = carregar_dados()
                        # Atualiza o Tipo das ordens selecionadas para "Ordens Criadas"
                        for cid in ids_para_priorizar:
                            df_atual.loc[pd.to_numeric(df_atual["ID"], errors="coerce") == cid, "Tipo"] = "Ordens Criadas"
                        
                        salvar_dados(df_atual)
                        st.success(f"{len(ids_para_priorizar)} ordem(ns) priorizada(s) com sucesso!")
                        st.rerun()

            with col_ctrl_ord3:
                if st.button("🗑️ Excluir Selecionadas", type="primary", use_container_width=True):
                    ids_para_excluir = []
                    for _, row in df_cadastradas_pagina.iterrows():
                        cid = int(row["ID"])
                        if st.session_state.get(f"chk_cad_{cid}", False):
                            ids_para_excluir.append(cid)

                    if not ids_para_excluir:
                        st.warning("Nenhuma ordem foi selecionada para exclusão!")
                    else:
                        if excluir_ordens_por_ids(ids_para_excluir):
                            st.success(f"{len(ids_para_excluir)} ordem(ns) excluída(s) com sucesso!")
                            st.rerun()

            st.markdown(f"<p style='color: gray; font-size: 12px; margin: 2px 0;'>Mostrando itens <strong>{inicio_ord+1} a {fim_ord}</strong> de <strong>{total_cadastradas}</strong></p>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 4px 0 6px 0;'>", unsafe_allow_html=True)

            for _, row in df_cadastradas_pagina.iterrows():
                try:
                    current_id = int(row["ID"])
                except:
                    continue

                if f"chk_cad_{current_id}" not in st.session_state:
                    st.session_state[f"chk_cad_{current_id}"] = False

                # Lógica de estilização visual igual às outras abas
                is_agrupado = str(row.get("Agrupado", "Não")) == "Sim"
                is_prioridade = str(row["Tipo"]) == "Ordens Criadas"

                if is_agrupado:
                    borda_cor = "#0d6efd"
                    fundo_cor = "#e7f1ff"
                elif is_prioridade:
                    borda_cor = "#dc3545"
                    fundo_cor = "#fff5f5"
                else:
                    borda_cor = "#ced4da"
                    fundo_cor = "#ffffff"

                # Bolinha vermelha para código com mais de 1 registro no sistema
                qtd_duplicada = contagem_codigos.get(str(row["Codigo"]).strip(), 1)
                html_bolinha = (
                    '<span title="Existem outros registros com este mesmo código no sistema" '
                    'style="height: 10px; width: 10px; background-color: #dc3545; border-radius: 50%; '
                    'display: inline-block; margin-left: 6px; box-shadow: 0 0 4px #dc3545;"></span>'
                    if qtd_duplicada > 1 else ''
                )

                col_c1, col_c2 = st.columns([0.04, 0.96])
                with col_c1:
                    st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
                    st.checkbox("", key=f"chk_cad_{current_id}", label_visibility="collapsed")
                with col_c2:
                    st.markdown(
                        f"""
                        <div style="padding: 4px 8px; border: 1px solid {borda_cor}; background-color: {fundo_cor}; border-radius: 4px; margin-bottom: 4px; font-size: 13px;">
                            <span style="color: #6c757d; font-size: 11px;">ID: {current_id} | Data: {row['Data']} | Tipo: <strong>{row['Tipo']}</strong> | Carga: <strong>{row['Carga']}</strong> | Status: <strong>{row['Status']}</strong></span>
                            <div style="margin-top: 1px;">
                                <strong>Ordem:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Codigo']}</span>{html_bolinha} &nbsp;|&nbsp;
                                <strong>Perfil:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Perfis']}</span> &nbsp;|&nbsp;
                                <strong>Sobras:</strong> <span style="color: #28a745;">{row['Sobras']}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Nenhum item encontrado com os filtros aplicados.")
    else:
        st.info("Nenhuma ordem cadastrada ainda.")







# ==========================================
# ABA 2: SEPARAÇÃO CORTE
# ==========================================
with aba2:
    st.markdown("<h4 style='margin-top: 2px;'>Separação para o Corte</h4>", unsafe_allow_html=True)

    df_global = carregar_dados()
    if not df_global.empty and "Status" in df_global.columns:
        pendentes = df_global[df_global["Status"].astype(str).str.strip() == "Pendente"].copy()
    else:
        pendentes = pd.DataFrame()

    if pendentes.empty:
        st.info("Não há ordens pendentes para separação no momento.")
    else:
        pendentes = aplicar_filtros_e_ordenacao(pendentes, "separacao")

        pendentes["Prioridade_Ord"] = pendentes["Tipo"].apply(
            lambda x: 0 if str(x) == "Ordens Criadas" else 1
        )
        pendentes = pendentes.sort_values("Prioridade_Ord")

        total_pendentes = len(pendentes)
        
        if total_pendentes == 0:
            st.info("Nenhum item encontrado com os filtros aplicados.")
        else:
            contagem_codigos = df_global["Codigo"].astype(str).str.strip().value_counts().to_dict() if not df_global.empty else {}

            st.markdown(
                """
                <div style="background-color: #f1f3f5; padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; border: 1px solid #dee2e6;">
                    <span style="font-size: 14px; font-weight: bold; color: #333;">Painel de Ações em Lote</span>
                </div>
                """,
                unsafe_allow_html=True
            )

            inicio, fim, pagina_atual, total_paginas = criar_paginacao(total_pendentes, 20, "separacao")
            pendentes_pagina = pendentes.iloc[inicio:fim]

            col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([1.5, 1.8, 1.3, 1.3])
            
            with col_ctrl1:
                st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
                def atualizar_todos_checkboxes():
                    estado_desejado = st.session_state.get(f"master_chk_{pagina_atual}", False)
                    for _, r in pendentes_pagina.iterrows():
                        try:
                            st.session_state[f"chk_ordem_{int(r['ID'])}"] = estado_desejado
                        except:
                            pass

                marcar_todos = st.checkbox(
                    "Marcar/Desmarcar", 
                    key=f"master_chk_{pagina_atual}",
                    on_change=atualizar_todos_checkboxes
                )
            
            with col_ctrl2:
                destino_lote = st.selectbox(
                    "Enviar para:",
                    ["Policorte 1", "Policorte 2", "Policorte 3"],
                    key="destino_lote_select",
                    label_visibility="collapsed"
                )
            
            with col_ctrl3:
                btn_enviar_lote = st.button("🚀 Enviar", type="primary", use_container_width=True)

            with col_ctrl4:
                btn_agrupar = st.button("🔗 Agrupar OS", type="secondary", use_container_width=True)

            if btn_enviar_lote:
                ids_para_enviar = []
                for _, row in pendentes_pagina.iterrows():
                    try:
                        cid = int(row["ID"])
                        if st.session_state.get(f"chk_ordem_{cid}", False):
                            ids_para_enviar.append(cid)
                    except:
                        continue
                
                if not ids_para_enviar:
                    st.warning("Nenhuma ordem foi selecionada!")
                else:
                    df_atual = carregar_dados()
                    for cid in ids_para_enviar:
                        mask = pd.to_numeric(df_atual["ID"], errors="coerce") == cid
                        df_atual.loc[mask, "Status"] = "Em Corte"
                        df_atual.loc[mask, "Policorte"] = destino_lote
                    salvar_dados(df_atual)
                    st.success(f"{len(ids_para_enviar)} ordem(ns) enviada(s) para a {destino_lote}!")
                    st.rerun()

            # --- LÓGICA DE AGRUPAR CORRIGIDA PARA SUPABASE ---
            if btn_agrupar:
                ids_para_agrupar = []
                for _, row in pendentes_pagina.iterrows():
                    try:
                        cid = int(row["ID"])
                        if st.session_state.get(f"chk_ordem_{cid}", False):
                            ids_para_agrupar.append(cid)
                    except:
                        continue

                if len(ids_para_agrupar) < 2:
                    st.warning("Selecione pelo menos duas ordens para agrupar!")
                else:
                    df_atual = carregar_dados()
                    # Garante conversão segura de IDs
                    ids_num_series = pd.to_numeric(df_atual["ID"], errors="coerce")
                    df_selecionadas = df_atual[ids_num_series.isin(ids_para_agrupar)]
                    
                    codigos_unicos = df_selecionadas["Codigo"].astype(str).str.strip().unique()
                    if len(codigos_unicos) > 1:
                        st.error("Erro: Você só pode agrupar ordens que possuem exatamente o mesmo **Código**!")
                    else:
                        id_principal = ids_para_agrupar[0]
                        ids_para_remover = ids_para_agrupar[1:]

                        perfis_combinados = {}
                        sobras_combinadas = {}

                        for _, r in df_selecionadas.iterrows():
                            p_dic = parse_string_itens(r["Perfis"])
                            for k, v in p_dic.items():
                                perfis_combinados[k] = perfis_combinados.get(k, 0) + v
                            
                            s_dic = parse_string_itens(r["Sobras"])
                            for k, v in s_dic.items():
                                sobras_combinadas[k] = sobras_combinadas.get(k, 0) + v

                        novo_texto_perfis = formatar_string_itens(perfis_combinados, "Perfil")
                        novo_texto_sobras = formatar_string_itens(sobras_combinadas, "Sobra")

                        # Atualiza o registro principal
                        mask_principal = pd.to_numeric(df_atual["ID"], errors="coerce") == id_principal
                        df_atual.loc[mask_principal, "Perfis"] = novo_texto_perfis
                        df_atual.loc[mask_principal, "Sobras"] = novo_texto_sobras
                        df_atual.loc[mask_principal, "Agrupado"] = "Sim"

                        # Salva a ordem unificada no Supabase
                        salvar_dados(df_atual[mask_principal])

                        # Deleta do Supabase as ordens secundárias que foram somadas
                        excluir_ordens_por_ids(ids_para_remover)

                        st.success(f"Ordens agrupadas com sucesso no ID {id_principal}!")
                        st.rerun()

            st.markdown(f"<p style='color: gray; font-size: 12px; margin: 2px 0;'>Mostrando itens <strong>{inicio+1} a {fim}</strong> de <strong>{total_pendentes}</strong> | Página {pagina_atual} de {total_paginas}</p>", unsafe_allow_html=True)
            st.markdown("<hr style='margin: 4px 0 6px 0;'>", unsafe_allow_html=True)

            for index, row in pendentes_pagina.iterrows():
                try:
                    current_id = int(row["ID"])
                except:
                    continue

                if f"chk_ordem_{current_id}" not in st.session_state:
                    st.session_state[f"chk_ordem_{current_id}"] = False

                is_agrupado = str(row.get("Agrupado", "Não")) == "Sim"
                is_prioridade = str(row["Tipo"]) == "Ordens Criadas"

                if is_agrupado:
                    borda_cor = "#0d6efd"
                    fundo_cor = "#e7f1ff"
                    cor_bolinha = "#0d6efd"
                    sombra_bolinha = "#0d6efd"
                    tooltip_bolinha = "Ordem agrupada com sucesso"
                elif is_prioridade:
                    borda_cor = "#dc3545"
                    fundo_cor = "#fff5f5"
                    cor_bolinha = "#dc3545"
                    sombra_bolinha = "#dc3545"
                    tooltip_bolinha = "Existem outros registros com este mesmo código no sistema"
                else:
                    borda_cor = "#ced4da"
                    fundo_cor = "#ffffff"
                    cor_bolinha = "#dc3545"
                    sombra_bolinha = "#dc3545"
                    tooltip_bolinha = "Existem outros registros com este mesmo código no sistema"

                qtd_duplicada = contagem_codigos.get(str(row["Codigo"]).strip(), 1)
                html_bolinha = f'<span title="{tooltip_bolinha}" style="height: 10px; width: 10px; background-color: {cor_bolinha}; border-radius: 50%; display: inline-block; margin-left: 6px; box-shadow: 0 0 4px {sombra_bolinha};"></span>' if qtd_duplicada > 1 else ''

                col_chk, col_card, col_btn_edit = st.columns([0.03, 0.87, 0.10])
                
                with col_chk:
                    st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
                    st.checkbox("", key=f"chk_ordem_{current_id}", label_visibility="collapsed")
                
                with col_card:
                    st.markdown(
                        f"""
                        <div style="padding: 4px 8px; border: 1px solid {borda_cor}; background-color: {fundo_cor}; border-radius: 4px; margin-bottom: 4px; font-size: 13px;">
                            <span style="color: #6c757d; font-size: 11px;">ID: {current_id} | Data: {row['Data']} | Tipo: <strong>{row['Tipo']}</strong> | Carga: <strong>{row['Carga']}</strong></span>
                            <div style="margin-top: 1px;">
                                <strong>Ordem:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Codigo']}</span>{html_bolinha} &nbsp;|&nbsp;
                                <strong>Perfil:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Perfis']}</span> &nbsp;|&nbsp;
                                <strong>Sobras:</strong> <span style="color: #28a745;">{row['Sobras']}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                
                with col_btn_edit:
                    st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
                    if st.button("✏️", key=f"btn_edit_{current_id}", use_container_width=True):
                        st.session_state[f"editando_{current_id}"] = not st.session_state.get(f"editando_{current_id}", False)
                        st.rerun()

                if st.session_state.get(f"editando_{current_id}", False):
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background-color: #f8f9fa; padding: 8px 12px; border-radius: 6px; border: 1px dashed #0d6efd; margin-bottom: 6px;">
                                <span style="font-size: 13px; font-weight: bold; color: #0d6efd;">Editando Ordens do ID {current_id}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        perfis_dict = parse_string_itens(row["Perfis"])
                        sobras_dict = parse_string_itens(row["Sobras"])

                        novos_perfis_dict = {}
                        
                        perfis_orig_total = sum(perfis_dict.values()) if perfis_dict else 1
                        sobras_orig_total = sum(sobras_dict.values()) if sobras_dict else 0
                        fator_proporcao = (sobras_orig_total / perfis_orig_total) if perfis_orig_total > 0 else 0

                        cols_ed = st.columns(2)
                        with cols_ed[0]:
                            st.markdown("##### Perfis (Editáveis)")
                            for p_nome, p_qtd in perfis_dict.items():
                                key_num = f"input_perfil_{current_id}_{p_nome}"
                                if key_num not in st.session_state:
                                    st.session_state[key_num] = int(p_qtd)
                                
                                nova_qtd_p = st.number_input(f"Qtd para: {p_nome}", min_value=0, step=1, key=key_num)
                                novos_perfis_dict[p_nome] = nova_qtd_p

                        with cols_ed[1]:
                            st.markdown("##### Sobras (Ajuste Automático)")
                            novo_total_perfis = sum(novos_perfis_dict.values())
                            novo_total_sobras_calculado = round(novo_total_perfis * fator_proporcao)

                            novas_sobras_dict = {}
                            if sobras_dict:
                                proporcao_parcial = 1 / len(sobras_dict)
                                for s_nome in sobras_dict.keys():
                                    qtd_s = max(1, round(novo_total_sobras_calculado * proporcao_parcial))
                                    novas_sobras_dict[s_nome] = qtd_s
                                    st.info(f"**{s_nome}**: Qtd ajustada automaticamente para **{qtd_s}**")
                            else:
                                st.info("Nenhuma sobra cadastrada para este item.")

                        col_salvar, col_cancelar = st.columns([1, 1])
                        with col_salvar:
                            if st.button("💾 Salvar Alterações", key=f"salvar_edit_{current_id}", type="primary", use_container_width=True):
                                # 1. Calcula o que restou (diferença) para gerar a nova ordem
                                perfis_restantes = {}
                                for p_nome, p_qtd_orig in perfis_dict.items():
                                    p_qtd_novo = novos_perfis_dict.get(p_nome, 0)
                                    diff = p_qtd_orig - p_qtd_novo
                                    if diff > 0:
                                        perfis_restantes[p_nome] = diff

                                # 2. Calcula sobras proporcionais para a nova ordem (se houver)
                                sobras_restantes = {}
                                if perfis_restantes and sobras_dict:
                                    if perfis_orig_total > 0:
                                        total_perfil_restante = sum(perfis_restantes.values())
                                        for s_nome, s_qtd_orig in sobras_dict.items():
                                            s_qtd_restante = round(s_qtd_orig * (total_perfil_restante / perfis_orig_total))
                                            if s_qtd_restante > 0:
                                                sobras_restantes[s_nome] = s_qtd_restante

                                str_p_novo = formatar_string_itens(novos_perfis_dict, "Perfil")
                                str_s_novo = formatar_string_itens(novas_sobras_dict, "Sobra")

                                df_atual = carregar_dados()
                                mask_cur = pd.to_numeric(df_atual["ID"], errors="coerce") == current_id
                                
                                # Atualiza a ordem original com os novos valores editados
                                df_atual.loc[mask_cur, "Perfis"] = str_p_novo
                                df_atual.loc[mask_cur, "Sobras"] = str_s_novo

                                # 3. Se houver quantidade restante, cria um novo registro na tabela
                                novo_id_gerado = None
                                if perfis_restantes:
                                    max_id = pd.to_numeric(df_atual["ID"], errors="coerce").max()
                                    novo_id_gerado = int(max_id) + 1 if pd.notna(max_id) else 1
                                    
                                    str_p_restante = formatar_string_itens(perfis_restantes, "Perfil")
                                    str_s_restante = formatar_string_itens(sobras_restantes, "Sobra")
                                    
                                    nova_linha = {
                                        "ID": str(novo_id_gerado),
                                        "Data": row.get("Data", datetime.now().strftime("%d/%m/%Y %H:%M")),
                                        "Tipo": row.get("Tipo", "Ordens Criadas"),
                                        "Carga": row.get("Carga", ""),
                                        "Codigo": row.get("Codigo", ""),
                                        "Perfis": str_p_restante,
                                        "Sobras": str_s_restante,
                                        "Status": "Pendente",
                                        "Policorte": "Nenhuma",
                                        "Agrupado": "Não"
                                    }
                                    df_atual = pd.concat([df_atual, pd.DataFrame([nova_linha])], ignore_index=True)

                                salvar_dados(df_atual)
                                st.session_state[f"editando_{current_id}"] = False
                                
                                if novo_id_gerado:
                                    st.success(f"Alterações salvas! Uma nova ordem (**ID {novo_id_gerado}**) foi gerada automaticamente com o restante da quantidade.")
                                else:
                                    st.success("Ordem atualizada com sucesso!")
                                st.rerun()

                        with col_cancelar:
                            if st.button("❌ Cancelar", key=f"cancel_edit_{current_id}", use_container_width=True):
                                st.session_state[f"editando_{current_id}"] = False
                                st.rerun()


                                
# ==========================================
# ABAS 3, 4 e 5: POLICORTES 1, 2 e 3
# ==========================================
for aba_obj, nome_poli in zip([aba3, aba4, aba5], ["Policorte 1", "Policorte 2", "Policorte 3"]):
    with aba_obj:
        st.markdown(f"<h4 style='margin-top: 2px;'>Fila de Trabalho - {nome_poli}</h4>", unsafe_allow_html=True)

        df_global = carregar_dados()
        if not df_global.empty and "Policorte" in df_global.columns and "Status" in df_global.columns:
            filtradas = df_global[
                (df_global["Policorte"].astype(str).str.strip() == nome_poli)
                & (df_global["Status"].astype(str).str.strip() == "Em Corte")
            ]
        else:
            filtradas = pd.DataFrame()

        if filtradas.empty:
            st.info(f"Nenhuma ordem no momento para a {nome_poli}.")
        else:
            filtradas = aplicar_filtros_e_ordenacao(filtradas, nome_poli.lower().replace(" ", "_"))
            total_filtradas = len(filtradas)

            if total_filtradas == 0:
                st.info("Nenhum item encontrado com os filtros aplicados.")
            else:
                contagem_codigos = df_global["Codigo"].astype(str).str.strip().value_counts().to_dict() if not df_global.empty else {}
                chave_poli_slug = nome_poli.lower().replace(" ", "_")
                inicio, fim, _, _ = criar_paginacao(total_filtradas, 20, chave_poli_slug)
                filtradas_pagina = filtradas.iloc[inicio:fim]

                st.markdown(f"<p style='color: gray; font-size: 12px; margin: 2px 0;'>Mostrando itens <strong>{inicio+1} a {fim}</strong> de <strong>{total_filtradas}</strong></p>", unsafe_allow_html=True)

                for index, row in filtradas_pagina.iterrows():
                    try:
                        current_id = int(row["ID"])
                    except:
                        continue

                    is_agrupado = str(row.get("Agrupado", "Não")) == "Sim"
                    is_prioridade = str(row["Tipo"]) == "Ordens Criadas"

                    if is_agrupado:
                        borda_cor = "#0d6efd"
                        fundo_cor = "#e7f1ff"
                        cor_bolinha = "#0d6efd"
                        sombra_bolinha = "#0d6efd"
                        tooltip_bolinha = "Ordem agrupada com sucesso"
                    elif is_prioridade:
                        borda_cor = "#dc3545"
                        fundo_cor = "#fff5f5"
                        cor_bolinha = "#dc3545"
                        sombra_bolinha = "#dc3545"
                        tooltip_bolinha = "Existem outros registros com este mesmo código no sistema"
                    else:
                        borda_cor = "#ced4da"
                        fundo_cor = "#ffffff"
                        cor_bolinha = "#dc3545"
                        sombra_bolinha = "#dc3545"
                        tooltip_bolinha = "Existem outros registros com este mesmo código no sistema"

                    qtd_duplicada = contagem_codigos.get(str(row["Codigo"]).strip(), 1)
                    html_bolinha = f'<span title="{tooltip_bolinha}" style="height: 10px; width: 10px; background-color: {cor_bolinha}; border-radius: 50%; display: inline-block; margin-left: 6px; box-shadow: 0 0 4px {sombra_bolinha};"></span>' if qtd_duplicada > 1 else ''

                    col_card, col_btn1, col_btn2 = st.columns([0.70, 0.15, 0.15])
                    with col_card:
                        st.markdown(
                            f"""
                            <div style="padding: 4px 8px; border: 1px solid {borda_cor}; background-color: {fundo_cor}; border-radius: 4px; margin-bottom: 4px; font-size: 13px;">
                                <span style="color: #6c757d; font-size: 11px;">ID: {current_id} | Tipo: <strong>{row['Tipo']}</strong> | Carga: {row['Carga']}</span>
                                <div style="margin-top: 1px;">
                                    <strong>Ordem:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Codigo']}</span>{html_bolinha} | 
                                    <strong>Perfil:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Perfis']}</span> | 
                                    <strong>Sobras:</strong> <span style="color: #28a745;">{row['Sobras']}</span>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with col_btn1:
                        if st.button("⬅️️ Voltar", key=f"vol_{nome_poli}_{current_id}", use_container_width=True):
                            df_atual = carregar_dados()
                            df_atual.loc[pd.to_numeric(df_atual["ID"], errors="coerce") == current_id, "Status"] = "Pendente"
                            df_atual.loc[pd.to_numeric(df_atual["ID"], errors="coerce") == current_id, "Policorte"] = "Nenhuma"
                            salvar_dados(df_atual)
                            st.success(f"ID {current_id} voltou para Separação!")
                            st.rerun()
                    with col_btn2:
                        if st.button("Finalizar", key=f"fin_{nome_poli}_{current_id}", use_container_width=True):
                            df_atual = carregar_dados()
                            df_atual.loc[pd.to_numeric(df_atual["ID"], errors="coerce") == current_id, "Status"] = "Finalizado"
                            salvar_dados(df_atual)
                            st.success(f"ID {current_id} finalizado!")
                            st.rerun()

# ==========================================
# ABA 6: FINALIZADAS
# ==========================================
with aba6:
    st.markdown("<h4 style='margin-top: 2px;'>Histórico de Ordens Finalizadas</h4>", unsafe_allow_html=True)

    df_global = carregar_dados()
    if not df_global.empty and "Status" in df_global.columns:
        finalizadas = df_global[df_global["Status"].astype(str).str.strip() == "Finalizado"].copy()
    else:
        finalizadas = pd.DataFrame()

    if finalizadas.empty:
        st.info("Ainda não há ordens finalizadas.")
    else:
        finalizadas = aplicar_filtros_e_ordenacao(finalizadas, "finalizadas")

        finalizadas["ID_num"] = pd.to_numeric(finalizadas["ID"], errors="coerce")
        finalizadas = finalizadas.sort_values("ID_num", ascending=True).drop(columns=["ID_num"])

        total_finalizadas = len(finalizadas)
        
        if total_finalizadas == 0:
            st.info("Nenhum item encontrado com os filtros aplicados.")
        else:
            contagem_codigos = df_global["Codigo"].astype(str).str.strip().value_counts().to_dict() if not df_global.empty else {}
            inicio, fim, _, _ = criar_paginacao(total_finalizadas, 20, "finalizadas")
            finalizadas_pagina = finalizadas.iloc[inicio:fim]

            st.markdown(f"<p style='color: gray; font-size: 12px; margin: 2px 0;'>Mostrando registros <strong>{inicio+1} a {fim}</strong> de <strong>{total_finalizadas}</strong></p>", unsafe_allow_html=True)
            
            for index, row in finalizadas_pagina.iterrows():
                try:
                    current_id = int(row["ID"])
                except:
                    continue

                is_agrupado = str(row.get("Agrupado", "Não")) == "Sim"
                is_prioridade = str(row["Tipo"]) == "Ordens Criadas"

                if is_agrupado:
                    borda_cor = "#0d6efd"
                    fundo_cor = "#e7f1ff"
                    cor_bolinha = "#0d6efd"
                    sombra_bolinha = "#0d6efd"
                    tooltip_bolinha = "Ordem agrupada com sucesso"
                elif is_prioridade:
                    borda_cor = "#dc3545"
                    fundo_cor = "#fff5f5"
                    cor_bolinha = "#dc3545"
                    sombra_bolinha = "#dc3545"
                    tooltip_bolinha = "Existem outros registros com este mesmo código no sistema"
                else:
                    borda_cor = "#ced4da"
                    fundo_cor = "#ffffff"
                    cor_bolinha = "#dc3545"
                    sombra_bolinha = "#dc3545"
                    tooltip_bolinha = "Existem outros registros com este mesmo código no sistema"

                qtd_duplicada = contagem_codigos.get(str(row["Codigo"]).strip(), 1)
                html_bolinha = f'<span title="{tooltip_bolinha}" style="height: 10px; width: 10px; background-color: {cor_bolinha}; border-radius: 50%; display: inline-block; margin-left: 6px; box-shadow: 0 0 4px {sombra_bolinha};"></span>' if qtd_duplicada > 1 else ''

                col_card, col_btn = st.columns([0.85, 0.15])
                with col_card:
                    st.markdown(
                        f"""
                        <div style="padding: 4px 8px; border: 1px solid {borda_cor}; background-color: {fundo_cor}; border-radius: 4px; margin-bottom: 4px; font-size: 13px;">
                            <span style="color: #6c757d; font-size: 11px;">ID: {current_id} | Data: {row['Data']} | Tipo: <strong>{row['Tipo']}</strong> | Carga: {row['Carga']} | Policorte: {row['Policorte']}</span>
                            <div style="margin-top: 1px;">
                                <strong>Ordem:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Codigo']}</span>{html_bolinha} | 
                                <strong>Perfil:</strong> <span style="color: #0056b3; font-weight: bold;">{row['Perfis']}</span> | 
                                <strong>Sobras:</strong> <span style="color: #28a745;">{row['Sobras']}</span>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_btn:
                    if st.button("⬅️ Voltar", key=f"vol_fin_{current_id}", use_container_width=True):
                        df_atual = carregar_dados()
                        df_atual.loc[pd.to_numeric(df_atual["ID"], errors="coerce") == current_id, "Status"] = "Pendente"
                        df_atual.loc[pd.to_numeric(df_atual["ID"], errors="coerce") == current_id, "Policorte"] = "Nenhuma"
                        salvar_dados(df_atual)
                        st.success(f"ID {current_id} voltou para Separação!")
                        st.rerun()

            st.markdown("<div style='height: 2px;'></div>", unsafe_allow_html=True)
            csv_export = finalizadas.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Baixar Relatório Completo de Finalizadas (CSV)",
                data=csv_export,
                file_name="ordens_finalizadas.csv",
                mime="text/csv",
            )

# ==========================================
# ABA 7: ANÁLISE DE CARGAS
# ==========================================
with aba7:
    st.markdown("<h4 style='margin-top: 2px;'>📊 Painel de Análise e Andamento de Cargas</h4>", unsafe_allow_html=True)

    df_global_analise = carregar_dados()

    if df_global_analise.empty:
        st.info("Nenhum dado registrado para exibir na análise.")
    else:
        data_hoje_str = datetime.now().strftime("%d/%m/%Y")
        df_global_analise["Data_Apenas"] = df_global_analise["Data"].astype(str).str.slice(0, 10)
        
        cargas_str = df_global_analise["Carga"].astype(str).str.strip().str.lower()
        sem_carga = (df_global_analise["Carga"].isna()) | (cargas_str == "") | (cargas_str == "nan") | (cargas_str == "none")
        
        ordens_hoje_sem_carga = df_global_analise[
            df_global_analise["Data_Apenas"].str.contains(datetime.now().strftime("%d/%m/%Y"), na=False) & sem_carga
        ]
        total_hoje = len(ordens_hoje_sem_carga)

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 6px 10px; border-radius: 6px; text-align: center;">
                    <span style="font-size: 11px; color: #6c757d; font-weight: bold;">📅 Data Atual</span>
                    <div style="font-size: 15px; font-weight: bold; color: #333; margin-top: 1px;">{data_hoje_str}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_m2:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 6px 10px; border-radius: 6px; text-align: center;">
                    <span style="font-size: 11px; color: #6c757d; font-weight: bold;">📥 Ordens Criadas Hoje (Sem Carga)</span>
                    <div style="font-size: 15px; font-weight: bold; color: #0d6efd; margin-top: 1px;">{total_hoje}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_m3:
            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; padding: 6px 10px; border-radius: 6px; text-align: center;">
                    <span style="font-size: 11px; color: #6c757d; font-weight: bold;">📦 Total Geral de Registros</span>
                    <div style="font-size: 15px; font-weight: bold; color: #333; margin-top: 1px;">{len(df_global_analise)}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 📈 Andamento por Carga e Ordens Criadas")

        df_global_analise["Carga_Limpa"] = df_global_analise["Carga"].astype(str).str.strip()
        mask_validas = ~df_global_analise["Carga_Limpa"].str.lower().isin(["", "nan", "none"])
        
        cargas_unicas = sorted([str(c) for c in df_global_analise.loc[mask_validas, "Carga_Limpa"].unique()])
        
        df_sem_carga_geral = df_global_analise[~mask_validas]
        if not df_sem_carga_geral.empty:
            cargas_unicas.insert(0, "📌 Ordens Criadas / Avulsas")

        for carga in cargas_unicas:
            if carga == "📌 Ordens Criadas / Avulsas":
                df_carga = df_sem_carga_geral
            else:
                df_carga = df_global_analise[df_global_analise["Carga_Limpa"] == carga]
            
            total_carga = len(df_carga)
            if total_carga == 0:
                continue

            q_separacao = len(df_carga[df_carga["Status"].astype(str).str.strip() == "Pendente"])
            q_corte = len(df_carga[df_carga["Status"].astype(str).str.strip() == "Em Corte"])
            q_finalizadas = len(df_carga[df_carga["Status"].astype(str).str.strip() == "Finalizado"])

            porcentagem_cortado = int((q_finalizadas / total_carga) * 100) if total_carga > 0 else 0

            st.markdown(
                f"""
                <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; border-left: 5px solid #0d6efd; padding: 8px 14px; border-radius: 6px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 15px; font-weight: bold; color: #0d6efd;">{carga}</span>
                        <span style="background-color: #0d6efd; color: #ffffff; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">Progresso: {porcentagem_cortado}% Concluído</span>
                    </div>
                    <div style="margin-top: 4px; font-size: 12px; color: #495057; display: flex; gap: 15px;">
                        <span>📋 Total: <strong>{total_carga}</strong></span>
                        <span>⏳ Em Separação: <strong style="color: #fd7e14;">{q_separacao}</strong></span>
                        <span>⚙️ Em Corte: <strong style="color: #ffc107;">{q_corte}</strong></span>
                        <span>✅ Finalizadas: <strong style="color: #28a745;">{q_finalizadas}</strong></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.progress(porcentagem_cortado / 100)