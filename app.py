import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd
import pandas as pd
import calendar


# Carregar os dados
df_crimes_base = pd.read_csv('crimesPOA_15_12_24.csv')
df_crimes = df_crimes_base.copy()
df_crimes["Local Fato"] = df_crimes["Local Fato"].apply(lambda x: x.replace("estabelecimento", "est."))

# Carregar os dados
data_geo_base = gpd.read_file("data_geo.shp")
data_geo_base["geometry"] = data_geo_base.simplify(200)

def format_name(name):
    exceptions = {"e", "de", "do", "da", "dos", "das"}
    words = name.split()
    formatted_words = [
        word.capitalize() if word.lower() not in exceptions else word.lower()
        for word in words
    ]
    return " ".join(formatted_words)

# Aplicar a formatação à coluna "CBairro"
data_geo_base["Bairro"] = data_geo_base["Bairro"].apply(format_name)


# Garantir que "Data Fato" seja tratada como datetime
df_crimes['Data Fato'] = pd.to_datetime(df_crimes['Data Fato'], format='%d/%m/%Y')

calendario = pd.DataFrame({'Data': pd.date_range(start=df_crimes['Data Fato'].min(), end=df_crimes['Data Fato'].max(), freq='D')})
# Criar colunas auxiliares no calendário
calendario['Ano'] = calendario['Data'].dt.year
calendario['Mes-Ano'] = calendario['Data'].dt.month
calendario['Dia da Semana'] = calendario['Data'].dt.weekday.map(
        {0: 'segunda', 1: 'terça', 2: 'quarta', 3: 'quinta', 4: 'sexta', 5: 'sábado', 6: 'domingo'}
    )
calendario['Mensal'] = calendario['Data'].dt.to_period('M').astype(str)

def agreg_tempo(df, selected_tempo, selected_bairro):
    

    # Combinar o DataFrame original com o calendário para incluir dias sem registros
    df = calendario.merge(df, left_on='Data', right_on='Data Fato', how='left')

    # Função para calcular a média diária por bairro
    def calcular_media_por_bairro(df):
        if selected_tempo == 'Ano' or selected_tempo is None:
            dias_por_ano = calendario.groupby('Ano')['Data'].count()  # Contar dias por ano
            aggregated_data = (
                df.groupby(['Ano', 'CBairro'])
                .agg(Crimes=('Incidente_ID', 'nunique'))
                .reindex(pd.MultiIndex.from_product(
                    [dias_por_ano.index, df['CBairro'].unique()], names=['Ano', 'CBairro']), fill_value=0
                )  # Garantir todos os anos e bairros
                .reset_index()
                .assign(Media=lambda x: x['Crimes'] / dias_por_ano[x['Ano']].values)
            )
            
            return aggregated_data, 'Ano'
        
        elif selected_tempo == 'Mensal':
            dias_por_mes_ano = calendario.groupby('Mensal')['Data'].count()  # Contar dias por mês/ano
            aggregated_data = (
                df.groupby(['Mensal', 'CBairro'])
                .agg(Crimes=('Incidente_ID', 'nunique'))
                .reindex(pd.MultiIndex.from_product(
                    [dias_por_mes_ano.index, df['CBairro'].unique()], names=['Mensal', 'CBairro']), fill_value=0
                )
                .reset_index()
                .assign(Media=lambda x: x['Crimes'] / dias_por_mes_ano[x['Mensal']].values)
            )
            
            # Alterar o formato para notação numérica do mês
            aggregated_data['Mensal'] = pd.to_datetime(aggregated_data['Mensal'], format='%Y-%m')#.dt.strftime('%m/%Y')
            return aggregated_data, 'Mensal'
        
        elif selected_tempo == 'Mes-Ano':
            dias_por_mes = calendario.groupby('Mes-Ano')['Data'].count()  # Contar dias por mês
            aggregated_data = (
                df.groupby(['Mes-Ano', 'CBairro'])
                .agg(Crimes=('Incidente_ID', 'nunique'))
                .reindex(pd.MultiIndex.from_product(
                    [dias_por_mes.index, df['CBairro'].unique()], names=['Mes-Ano', 'CBairro']), fill_value=0
                )
                .reset_index()
                .assign(Media=lambda x: x['Crimes'] / dias_por_mes[x['Mes-Ano']].values)
            )
            aggregated_data['Mes-Ano'] = aggregated_data['Mes-Ano'].apply(
                lambda x: pd.to_datetime(f'2023-{x:02d}-01').strftime('%b')
            )
            meses_ordenados = list(calendar.month_abbr[1:]),
            aggregated_data['Mes-Ano'] = pd.Categorical(
                aggregated_data['Mes-Ano'], 
                categories=meses_ordenados, 
                ordered=True
            )
            return aggregated_data, 'Mes-Ano'
        
        elif selected_tempo == 'Dia da Semana':
            dias_por_dia_semana = calendario['Dia da Semana'].value_counts()
            aggregated_data = (
                df.groupby(['Dia da Semana', 'CBairro'])
                .agg(Crimes=('Incidente_ID', 'nunique'))
                .reindex(pd.MultiIndex.from_product(
                    [dias_por_dia_semana.index, df['CBairro'].unique()], names=['Dia da Semana', 'CBairro']), fill_value=0
                )
                .reset_index()
                .assign(Media=lambda x: x['Crimes'] / dias_por_dia_semana[x['Dia da Semana']].values)
            )
            dias_ordenados = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']
            aggregated_data['Dia da Semana'] = pd.Categorical(
                aggregated_data['Dia da Semana'], 
                categories=dias_ordenados, 
                ordered=True
            )
            aggregated_data = aggregated_data.sort_values('Dia da Semana')
            return aggregated_data, 'Dia da Semana'

        elif selected_tempo == 'Hora do Dia':
            # Verificar se a coluna 'Hora Fato' existe
            if 'Hora Fato' in df.columns:
                # Converter 'Hora Fato' para o formato timedelta
                df['Hora Fato'] = pd.to_timedelta(df['Hora Fato'], errors='coerce')
                df['Hora'] = df['Hora Fato'].dt.total_seconds() // 3600  # Extrai a hora como inteiro
            else:
                raise ValueError("A coluna 'Hora Fato' não está disponível no DataFrame para calcular a hora.")

            # Criar um calendário de horas (0 a 23) para garantir que todas as horas sejam consideradas
            horas = pd.DataFrame({'Hora': range(0, 24)})

            # Adicionar bairros ao calendário de horas
            bairros = df['CBairro'].unique()
            calendario_horas = pd.MultiIndex.from_product([horas['Hora'], bairros], names=['Hora', 'CBairro'])

            # Agregar os dados considerando as horas e os bairros
            aggregated_data = (
                df.groupby(['Hora', 'CBairro'])
                .agg(Crimes=('Incidente_ID', 'nunique'))
                .reindex(calendario_horas, fill_value=0)
                .reset_index()
            )

            # Calcular a média por hora
            dias_unicos = calendario['Data'].dt.date.nunique()  # Número de dias únicos no calendário
            aggregated_data['Media'] = aggregated_data['Crimes'] / dias_unicos

            return aggregated_data, 'Hora'

    # Média diária por bairro
    bairro_data, x_col = calcular_media_por_bairro(df)

    # Calcular a média diária por bairro
    all_bairros_data = (
        bairro_data.groupby(x_col)['Media']
        .mean()
        .reset_index()
        .rename(columns={'Media': 'Medias'})
    )
    all_bairros_data['Tipo'] = 'Todos os Bairros'

    # Dados do bairro selecionado
    if selected_bairro != None:
        selected_bairro_data = bairro_data[bairro_data['CBairro'] == selected_bairro].copy()
        selected_bairro_data = selected_bairro_data.groupby(x_col)['Media'].mean().reset_index()
        selected_bairro_data['Tipo'] = selected_bairro
        selected_bairro_data = selected_bairro_data.rename(columns={'Media': 'Medias'})

        # Combinar os dados
        combined_data = pd.concat([all_bairros_data, selected_bairro_data], ignore_index=True)
    else:
        combined_data = all_bairros_data
    

    return combined_data, x_col

def fig_update(fig): # Personalizações adicionais
        fig = fig.update_layout(
        plot_bgcolor='white',  # Fundo branco
        xaxis=dict(showgrid=False),  # Remove linhas internas do eixo X
        yaxis=dict(showgrid=False) # Remove linhas internas do eixo Y
        )
        return(fig)

def grapher_bairro(df,selected_bairro,selected_crime):
    # Atualizar os dados de bairros e calcular o ranking
    crimes_bairro = (
        df.groupby('CBairro')['Incidente_ID']
        .nunique()
        .reset_index(name='Incidentes')
        .sort_values(by="Incidentes", ascending=False)
        .reset_index(drop=True)
    )
    crimes_bairro["Ranking"] = crimes_bairro.index + 1  # Adicionar coluna de ranking

    # Selecionar os Top 5 bairros
    top_bairros = crimes_bairro.nlargest(5, "Incidentes")

    if selected_bairro is None:
        fig_bairro = px.bar(
            top_bairros,
            x="CBairro",  # Exibir o nome modificado
            y="Incidentes",
            hover_name="CBairro",
            hover_data=["Incidentes", "Ranking"],
            labels={'Incidentes': 'Número de incidentes', 'CBairro': 'Bairro', 'Métrica': 'Legenda'},
            text="Incidentes",  # Incluir os valores no gráfico
        )
        fig_bairro.update_traces(marker_color='darkgray')
        fig_bairro.update_layout(
        yaxis=dict(showticklabels=False)
        )

    else:
    # Garantir que o bairro selecionado seja incluído
        if selected_bairro not in top_bairros["CBairro"].values:
            bairro_destaque = crimes_bairro[crimes_bairro["CBairro"] == selected_bairro]
            if not bairro_destaque.empty:
                top_bairros = pd.concat([top_bairros, bairro_destaque])

        # Remover duplicatas e reorganizar
        top_bairros = top_bairros.drop_duplicates().sort_values(by="Incidentes", ascending=False)

        # Atualizar o nome dos bairros com o ranking para exibição
        top_bairros["NomeExibicao"] = top_bairros.apply(
            lambda row: f"{row['CBairro']} ({row['Ranking']}º)" if row["CBairro"] == selected_bairro else row["CBairro"],
            axis=1
        )

        # Adicionar coluna de destaque usando o nome original (não modificado)
        top_bairros["Destaque"] = top_bairros["CBairro"].apply(
            lambda x: selected_bairro if x == selected_bairro else "Todos os bairros"
        )

        fig_bairro = px.bar(
        top_bairros,
        x="NomeExibicao",  # Exibir o nome modificado
        y="Incidentes",
        color="Destaque",  # Colorir com base no destaque
        color_discrete_map={selected_bairro: "firebrick", "Todos os bairros": "darkgray"},
        hover_name="CBairro",
        labels={'Incidentes': 'Número de incidentes', 'NomeExibicao': 'Bairro', 'Métrica': 'Legenda'},
        text="Incidentes"  # Incluir os valores no gráfico
        )

        # Personalizar layout e traços
        fig_bairro.update_traces(
        textposition='inside',  # Coloca os valores dentro das colunas
        textfont=dict(size=10),  # Define o tamanho da fonte dos textos
        )
        fig_bairro.update_layout(
        yaxis=dict(showticklabels=False),
        showlegend=False,
    )
        


# Configuração do layout
    fig_bairro = fig_update(fig_bairro)
    fig_bairro = fig_bairro.update_layout(margin=dict(r=10,l=10,t=10,b=10)) 
    return(fig_bairro)

def grapher_local(df,selected_bairro,selected_crime):
    crimes_local_bairro = df.groupby(['Local Fato','CBairro'])['Incidente_ID'].nunique().reset_index(name='Incidentes_Bairro')
    
    df_local_med = crimes_local_bairro[crimes_local_bairro['CBairro'] != selected_bairro].copy()
    df_local_med = df_local_med.groupby('Local Fato')['Incidentes_Bairro'].mean().reset_index(name='Incidentes_Bairro')
    df_local_med['Todos os bairros'] = (df_local_med['Incidentes_Bairro'] / df_local_med['Incidentes_Bairro'].sum()) * 100
    
    if selected_bairro is None:
        # Long-form
        grafico_df = df_local_med.sort_values(by='Incidentes_Bairro', ascending=True).melt(id_vars='Local Fato', value_vars='Todos os bairros', 
                                var_name='Métrica', value_name='Valor')
             
        fig_local = px.bar(
                grafico_df,
                y='Local Fato',
                x='Valor',
                barmode='group',
                text = 'Valor',
                text_auto='.1f',
                labels={'Valor': 'Participação (%)', 'Crime': 'Tipo de Crime', 'Métrica': 'Legenda'}
                )
        fig_local = fig_local.update_layout(
            height=700,  # Ajuste a altura do gráfico
            margin=dict(r=10,l=10,t=10,b=10),  # Ajuste as margens para melhor visualização
            xaxis=dict(showticklabels=False)
        )
        fig_local.update_traces(marker_color='darkgray',
        texttemplate='%{text:.1f}%',  # Formato do texto com uma casa decimal e símbolo de porcentagem
        hovertemplate="Local: %{y}<br>Participação: %{x:,.1f}%<extra></extra>"  # Formato do hovertext
        )


    else:
        # Filtro do bairro alvo
        df_local_alvo = crimes_local_bairro[crimes_local_bairro['CBairro'] == selected_bairro].copy()
        df_local_alvo[selected_bairro] = (df_local_alvo['Incidentes_Bairro'] / df_local_alvo['Incidentes_Bairro'].sum()) * 100
        df_local = pd.merge(df_local_alvo, df_local_med, on='Local Fato', how='outer').fillna(0)

        # Long-form para facilitar a personalização
        grafico_df = df_local.melt(id_vars='Local Fato', value_vars=[selected_bairro, 'Todos os bairros'], 
                                    var_name='Métrica', value_name='Valor')
        
        cores = {
            selected_bairro: 'firebrick',  # Chave corresponde ao nome do bairro
            'Todos os bairros': 'darkgray'
        }
        
        fig_local = px.bar(
        grafico_df,
        x='Valor',
        y='Local Fato',
        color='Métrica',
        color_discrete_map=cores,
        barmode='group',
        text = 'Valor',
        text_auto='.1f',
        labels={'Valor': 'Participação (%)', 'Crime': 'Tipo de Crime', 'Métrica': 'Legenda'},
        )        
        fig_local.update_layout(
            margin=dict(r=10,l=10,t=10,b=10),  # Ajuste as margens para melhor visualização
            xaxis=dict(showticklabels=False),
            legend=dict(
            title="Legenda",
                orientation="h",       # Horizontal
                yanchor="bottom",      # Alinhado ao fundo
                y=1,                 # Ajuste vertical (acima do gráfico)
                xanchor="center",      # Centralizado
                x=0.45                  # Ajuste horizontal
            )
            )
        
    fig_local = fig_update(fig_local)
    fig_local.update_traces(
        texttemplate='%{text:.1f}%',  # Formato do texto com uma casa decimal e símbolo de porcentagem
        hovertemplate="Local: %{y}<br>Participação: %{x:,.1f}%<extra></extra>"  # Formato do hovertext
        )
    return(fig_local)

def grapher_tipo(df,selected_bairro):
    total_crimes_por_bairro = df.groupby('CBairro')['Incidente_ID'].nunique().reset_index(name='Total_Incidentes')
    crimes_por_bairro_tipo = df.groupby(['Crime', 'CBairro'])['Incidente_ID'].nunique().reset_index(name='Incidentes_Bairro')
    
    if selected_bairro is None:
        
        grafico_df = crimes_por_bairro_tipo.groupby('Crime')['Incidentes_Bairro'].sum().reset_index(name='Média dos bairros').sort_values(by='Média dos bairros', ascending=True)
        grafico_df = grafico_df.melt(id_vars='Crime', value_vars='Todos os bairros', 
                                var_name='Métrica', value_name='Valor')
        
       # Criar o gráfico com barras horizontais
        fig_tipo = px.bar(
            grafico_df,
            y='Crime',
            x='Valor',
            text_auto='.f',
            text='Valor',
            labels={'Valor': 'Número de incidentes', 'Crime': 'Tipo de Crime'},
            
        )

        # Personalizações
        fig_tipo.update_traces(marker_color='darkgray')
        fig_tipo.update_layout(
            height=700,  # Ajuste a altura do gráfico
            margin=dict(r=10,l=10,t=10,b=10),  # Ajuste as margens para melhor visualização
            xaxis=dict(showticklabels=False)
        )

    else:
        
        df_participacao = pd.merge(crimes_por_bairro_tipo, total_crimes_por_bairro, on='CBairro')
        df_participacao['Participacao'] = (df_participacao['Incidentes_Bairro'] / df_participacao['Total_Incidentes']) * 100
        media_participacao = df_participacao.groupby('Crime')['Participacao'].mean().reset_index(name='Todos os bairros')
        participacao_bairro_alvo = df_participacao[df_participacao['CBairro'] == selected_bairro][['Crime', 'Participacao']].sort_values(by='Participacao', ascending=True)
        # Merge para combinar as informações
        grafico_df = pd.merge(participacao_bairro_alvo, media_participacao, on='Crime', how='outer').fillna(0)
        grafico_df.columns = grafico_df.columns.str.replace('Participacao', selected_bairro)

        # Long-form para facilitar a personalização
        grafico_df = grafico_df.melt(id_vars='Crime', value_vars=[selected_bairro, 'Todos os bairros'], 
                                    var_name='Métrica', value_name='Valor')
        
        cores = {
            selected_bairro: 'firebrick',  # Chave corresponde ao nome do bairro
            'Todos os bairros': 'darkgray'
        }

        fig_tipo = px.bar(
            grafico_df,
            x='Valor',
            y='Crime',
            color='Métrica',
            color_discrete_map=cores,
            barmode='group',
            text='Valor',
            text_auto='.2f',
            labels={'Valor': 'Participação (%)', 'Crime': 'Tipo de Crime', 'Métrica': 'Legenda'},
            #orientation="h",
        )

        # Personalizações
        
        fig_tipo.update_layout(
            yaxis={"dtick":1},
            height=700,  # Ajuste a altura do gráfico
            margin=dict(r=10,l=10,t=10,b=10),  # Ajuste as margens para melhor visualização
            xaxis=dict(showticklabels=False),
            legend=dict(
            title="Legenda",
                orientation="h",       # Horizontal
                yanchor="bottom",      # Alinhado ao fundo
                y=1,                 # Ajuste vertical (acima do gráfico)
                xanchor="center",      # Centralizado
                x=0.45                  # Ajuste horizontal
            )
        )
        fig_tipo.update_yaxes(type='category')
        fig_tipo.update_traces(
        texttemplate='%{text:.1f}%',  # Formato do texto com uma casa decimal e símbolo de porcentagem
        hovertemplate="Crime: %{y}<br>Participação: %{x:,.1f}%<extra></extra>"  # Formato do hovertext
        )
    

    # Personalizações adicionais
    fig_tipo = fig_update(fig_tipo)
    
    return(fig_tipo)

def grapher_tempo(df, x_col, selected_crime, selected_bairro, selected_tempo):
    if selected_tempo == 'Hora do Dia':
        fig_tempo = px.line(
            df,
            x=x_col,
            y='Medias',
            color="Tipo" if selected_bairro else None,  # Apenas diferencia as linhas se `selected_bairro` estiver definido
            color_discrete_map={'Todos os Bairros': 'darkgray', f"{selected_bairro}": 'firebrick'}
        )
    
        # Atualize o layout
        fig_tempo.update_layout(
            xaxis=dict(
                tickmode = 'linear',
                tick0 = 0,
                dtick = 2,
                title = 'Hora do Dia',
                showgrid=False
            ),
            yaxis=dict(showgrid=False),
            plot_bgcolor="white",
            hovermode='x unified',
            legend_title="Tipo" if selected_bairro else None,
            margin=dict(r=10,l=10,t=10,b=10),
            legend=dict(
                title="Legenda",
                orientation="h",       # Horizontal
                yanchor="bottom",      # Alinhado ao fundo
                y=1,                 # Ajuste vertical (acima do gráfico)
                xanchor="center",      # Centralizado
                x=0.5                  # Ajuste horizontal
            ) if selected_bairro else None
        )

    else:
        fig_tempo = px.line(
            df,
            x=x_col,
            y='Medias',
            color="Tipo" if selected_bairro else None,
            color_discrete_map={'Todos os Bairros': 'darkgray', f"{selected_bairro}": 'firebrick'}
        )
        
        fig_tempo.update_layout(
            xaxis=dict(
                tickmode='array',
                title='Periodo',
                showgrid=False
            ),
            yaxis=dict(showgrid=False),
            plot_bgcolor="white",
            hovermode='x unified',
            legend_title="Tipo" if selected_bairro else None,
            margin=dict(r=10,l=10,t=10,b=10),
            legend=dict(
                title="Legenda",
                orientation="h",       # Horizontal
                yanchor="bottom",      # Alinhado ao fundo
                y=1,                 # Ajuste vertical (acima do gráfico)
                xanchor="center",      # Centralizado
                x=0.5                  # Ajuste horizontal
            ) if selected_bairro else None
        )

    # Caso `selected_bairro` seja `None`, defina a cor manualmente para cinza
    if selected_bairro is None:
        fig_tempo.update_traces(line=dict(color='darkgray'))   
    
    if selected_tempo == 'Mensal':
        fig_tempo.update_xaxes(
            dtick="M3",
            tickformat="%b\n%Y",
            ticklabelmode="period")
    
    if selected_tempo == 'Ano':
        fig_tempo.update_xaxes(type='category')
    
    fig_tempo = fig_update(fig_tempo)
    fig_tempo.update_traces(
        texttemplate='{text:.3f}',  # Formato do texto com uma casa decimal e símbolo de porcentagem
        hovertemplate="Média: %{y:.3f}<br>Período: %{x}<extra></extra>"  # Formato do hovertext
        )
    
    
    return fig_tempo

dict_crimes = {"roubo/furto veiculo":"**Definição do tipo de crime:** Subtrair patrimônio sem o consentimento do proprietário, com ou sem uso de violência.\n **Exemplos:** Furto e roubo de meios de transporte motorizados em trânsito ou estacionados; furto e roubo de carga ou de bens do motoristas.",
 "homicidio":"**Definição do tipo de crime:** Causar a morte de uma pessoa de forma voluntária ou não.\n\n **Exemplos:** Homicídio culposo e doloso; latrocínio (roubo seguido de morte); mortes em acidentes de trânsito; lesão corporal seguida de morte; feminicídio.",
 "roubo/furto propriedade": "**Definição do tipo de crime:** Subtrair patrimônio sem o consentimento do proprietário, com ou sem uso de violência.\n\n **Exemplos:** Furto e roubo de casas e de diferentes tipos de estabelecimentos (comerciais, educacionais e religiosos); furto e roubo de fios, cabos e outros tipos de estruturas públicas e privadas; abigeato.",
 "furto": "**Definição do tipo de crime:** Subtrair bem alheio sem que haja violência.\n\n **Exemplos:** Furto simples ou qualificado; furto de pedestres; furto de carteira e celular.",
 "roubo": "**Definição do tipo de crime:** Subtrair bem alheio mediante ameaça ou violência.\n\n **Exemplos:** Roubo simples e qualificado; roubo de pedestres; roubo com lesão corporal; roubo seguido de morte, assalto à mão armada.",
 "crimes sexuais": "**Definição do tipo de crime:** Atentados contra a liberdade e dignidade sexual de uma pessoa.\n\n **Exemplos:** Importunação sexual; estupro; abuso de menor; gestos obscenos; divulgação de conteúdo sexual infantil ou sem consentimento da pessoa.",
 "ameaça/vias de fato":"**Definição do tipo de crime:** Ameaçar a integridade física de uma pessoa sem causar lesão corporal.\n\n **Exemplos:** Ameaça; vias de fato; perseguição; desobedecer medida protetiva; incitação à violência.",
 "lesao corporal":"**Definição do tipo de crime:** Delitos que atentam contra a integridade física e a vida de uma pessoa.\n\n **Exemplos:** Lesão corporal leve, grave e gravíssima; violência doméstica e contra a mulher; atropelamento; roubo com lesão corporal." 
 }
# Componente Markdown para exibir a explicação do crime
def render_explanation(selected_crime):
    if selected_crime in dict_crimes:
        # Exibe a explicação do crime selecionado
        return dcc.Markdown(dict_crimes[selected_crime],
            style={'whiteSpace': 'pre-line'}  # Garante a quebra de linha correta no Markdown
        )
    else:
        # Mensagem padrão caso nenhum crime seja selecionado
        return dcc.Markdown("**Selecione um tipo de crime para mais informações.**")


# Configurar a aplicação Dash
external_stylesheets = [dbc.themes.BOOTSTRAP]
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

title_bairro = ""
stitle_bairro = ""
title_tempo = " "
stitle_tempo = " "
title_tipo = " "
stitle_tipo = " "
title_local = " "
stitle_local = " "

fig_mapa = go.Figure()
fig_bairro = px.bar()
fig_tempo = px.line()
fig_tipo = px.bar()
fig_local = px.bar()

texto_bairro = ""

# Layout do Dash
app.layout = dbc.Container(
    [
        # Cabeçalho ou título do dashboard
        dbc.Row(
            [
                dbc.Col(html.H1("Mapa da criminalidade em Porto Alegre", style={"color": "firebrick"}), width=11),
                dbc.Col(html.P("Dados abertos da Secretaria de Segurança Pública do estado do Rio Grande do Sul (SSP-RS)", style={"color": "#666"}), width=11),
                dbc.Col(html.Hr(style={'borderWidth': "0.3vh", "width": "1px", "color": "#666","marginTop": "5px","marginBottom": "20px",})),
                dbc.Col(html.B("Veja a distribuição espacial e temporal dos crimes cometidos nos últimos anos na capital gaúcha, e compare o perfil de crimes dos bairros.", style={"color": "#666"}), width=11),
                dbc.Col(html.P("Este relatório interativo inclui dados dos principais tipos de delitos responsáveis pelo sentimento de insegurança e medo no cidadão, como furto, roubo e crimes que atentam contra a vida. Os dados compreendem ocorrências criminais individuais registradas pelas Polícias de Porto Alegre, e repassadas à SSP-RS, no período de outubro de 2021 até agosto de 2024. Foram considerados apenas dados com informações sobre o bairro das ocorrências, totalizando 293.311 registros.", style={"color": "#666", "gap": "10px"}), width=11),
            ],
            style={"textAlign": "center", "marginBottom": "20px","justifyContent": "center", "padding": "12px"},
        ),

        # Mapa na parte superior
        dbc.Row(
            dbc.Col(
                dcc.Graph(
                    figure=fig_mapa,
                    id="mapa-crimes",
                    config={"displayModeBar": False},
                    style={"height": "50vh"}  # Altura ajustável
                ),
                width=12,
            ),
            style={"marginBottom": "20px","justifyContent": "center", "padding": "10px","borderRadius": "5px"},
        ),

        # Filtros (dropdowns)
        dbc.Row(
            [
                dbc.Col(
                    dcc.Dropdown(
                        id="dp_1",
                        options=[{"label": bairro, "value": bairro} for bairro in sorted(df_crimes_base["CBairro"].unique())],
                        placeholder="Selecione um bairro",
                        style={"fontSize":"13px"}
                    ),
                    style={"backgroundColor": "#d3d3d3","padding": "10px", "borderRadius": "5px"},
                    sm=4,md=4
                ),
                dbc.Col(
                    dcc.Dropdown(
                        id="dp_2",
                        options=[{"label": crime, "value": crime} for crime in df_crimes_base["Crime"].unique()],
                        placeholder="Selecione um tipo de crime",
                        style={"fontSize":"13px"}
                    ),
                    style={"backgroundColor": "#d3d3d3","padding": "10px", "borderRadius": "5px"},
                    sm=4,md=4
                ),
            ],
            style={"marginBottom": "20px", "gap":"20px", "justifyContent": "center"},
        ),

        # Texto explicativo
        dbc.Row(
            dbc.Col(
                [
                    dcc.Markdown(f"{texto_bairro}", id="texto_bairro"),
                    html.P(id="markdown_explanation"),
                ],
                style={"textAlign": "center"},
                width=11,
            ),style={"justifyContent": "center", "marginBottom": "10px"}
        ),

        # Gráficos
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card([
                        html.B(title_bairro, id="title_bairro", style={"color": "#666", "height": "30px", "marginBottom": "3px", "fontSize": "13px"}),
                        html.P(stitle_bairro, id="stitle_bairro", style={"color": "#666", "height": "25px", "fontSize": "12px"}),
                        dcc.Graph(figure=fig_bairro, id="graph", responsive=True, style={"height": "50vh", "marginBottom": "5px"},config={"displayModeBar": False}),
                        ],
                        style={"backgroundColor": "white","marginBottom": "20px", "padding": "10px", "borderRadius": "5px"}),
                sm=11,md=5),
                dbc.Col(
                    dbc.Card(
                    [
                        html.B(title_tempo, id="title_tempo", style={"color": "#666", "height": "30px", "marginBottom": "3px", "fontSize": "13px"}),
                        html.P(stitle_tempo, id="stitle_tempo", style={"color": "#666", "height": "25px", "fontSize": "12px"}),
                        dcc.Graph(
                            figure=fig_tempo,
                            id="graph_tempo",
                            responsive=True,
                            style={"height": "44vh", "marginBottom": "5px"},
                            config={"displayModeBar": False}
                        ),
                        html.Div(
                            id="button-group",
                            style={
                                "display": "flex",
                                "justifyContent": "center",
                                "gap": "5px",
                                "backgroundColor": "white",
                                "marginTop": "5px",
                            },
                            children=[
                                html.Button("Anual", id="btn-ano", n_clicks=0, style={"fontSize": "10px", "height": "33px"}),
                                html.Button("Mensal", id="btn-mes-ano", n_clicks=1, style={"fontSize": "10px", "height": "33px"}),
                                html.Button("Mês(Ano)", id="btn-mes", n_clicks=0, style={"fontSize": "10px", "height": "33px"}),
                                html.Button("Dia da Semana", id="btn-dia-semana", n_clicks=0, style={"fontSize": "10px", "height": "33px"}),
                                html.Button("Hora do Dia", id="btn-hora-dia", n_clicks=0, style={"fontSize": "10px", "height": "33px"}),
                            ],
                        ),
                    ],
            style={"backgroundColor": "white", "padding": "10px", "borderRadius": "5px"},
                ),
                sm=11,
                md=5,
            ),
                         
            ],
            style={"marginBottom": "20px", "justifyContent": "center"},
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card([
                        html.B(title_tipo, id="title_tipo", style={"color": "#666", "height": "30px", "marginBottom": "3px", "fontSize": "13px"}),
                        html.P(stitle_tipo, id="stitle_tipo", style={"color": "#666", "height": "25px", "fontSize": "12px"}),
                        dcc.Graph(figure=fig_tipo, id="graph_tipo", responsive=True, style={"height": "65vh", "marginBottom": "5px"},config={"displayModeBar": False}),
                        ],
                        style={"backgroundColor": "white","marginBottom": "20px", "padding": "10px", "borderRadius": "5px"}
                        ),
                        sm=11,md=5),
                dbc.Col(
                    dbc.Card([
                        html.B(title_local, id="title_local", style={"color": "#666", "height": "30px", "marginBottom": "3px", "fontSize": "13px"}),
                        html.P(stitle_local, id="stitle_local", style={"color": "#666", "height": "25px", "fontSize": "12px"}),
                        dcc.Graph(figure=fig_local, id="graph_local", responsive=True, style={"height": "65vh", "marginBottom": "5px"},config={"displayModeBar": False}),
                        ],
                        style={"backgroundColor": "white", "padding": "10px", "borderRadius": "5px"}
                        ),
                        sm=11,md=5),
            ],
            style={"marginBottom": "20px", "justifyContent": "center"},
        ),
        dbc.Row(
            dbc.Col([
                html.P("Rômulo Vitória - Análise e Ciência de Dados", style={"color": "#666","fontSize": "12px"}),
                html.P("Contato: romulovitoria@gmail.com", style={"color": "#666","fontSize": "12px"}),
                html.A("Linkedin", href="https://www.linkedin.com/in/r%C3%B4mulo-vit%C3%B3ria-72602529a/",style={"color": "#666", "fontSize": "12px"}, target="_blank")
                ],
                width=12,
            ),
            style={"textAlign": "center","marginBottom": "5px","justifyContent": "center", "padding": "5px"},
        
        ),    
    
    ],
    fluid=True,
    style={"backgroundColor": "darkgray", "padding": "20px"},
)


@app.callback(
    [
        Output('texto_bairro','children'),
        Output("markdown_explanation", "children"),
        Output("title_bairro", "children"),
        Output("stitle_bairro", "children"),
        Output("graph", "figure"),  
        Output("title_tempo", "children"),
        Output("stitle_tempo", "children"),
        Output("graph_tempo", "figure"),
        Output("title_tipo", "children"),
        Output("stitle_tipo", "children"),
        Output("graph_tipo", "figure"),
        Output("title_local", "children"),
        Output("stitle_local", "children"),
        Output("graph_local", "figure"),
        
    
    ],
    [
        Input("dp_1", "value"),  # Bairro selecionado
        Input("dp_2", "value"),  # Crime selecionado
        Input("btn-ano", "n_clicks"),  # Botão Ano
        Input("btn-mes-ano", "n_clicks"),  # Botão Mês e Ano
        Input("btn-mes", "n_clicks"),  # Botão Mês
        Input("btn-dia-semana", "n_clicks"),  # Botão Dia da Semana
        Input("btn-hora-dia", "n_clicks"),  # Botão Hora do Dia        
    ]
)
def update_graphs(selected_bairro, selected_crime, btn_ano, btn_mes_ano, btn_mes, btn_dia_semana, btn_hora_dia):
    selected_tempo = 'Mensal'  # Valor padrão, caso nenhum botão tenha sido clicado
    ctx = dash.callback_context
# Verifica qual botão foi clicado
    if ctx.triggered:
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if triggered_id == "btn-ano":
            selected_tempo = "Ano"
        elif triggered_id == "btn-mes-ano":
            selected_tempo = "Mensal"
        elif triggered_id == "btn-mes":
            selected_tempo = "Mes-Ano"
        elif triggered_id == "btn-dia-semana":
            selected_tempo = "Dia da Semana"
        elif triggered_id == "btn-hora-dia":
            selected_tempo = "Hora do Dia"

    # Filtrar os dados pelo crime selecionado
    if selected_crime is None:
        filtered_df = df_crimes
        
    else:
        filtered_df = df_crimes[df_crimes["Crime"] == selected_crime]
        

    # Filtrar os dados pelo bairro selecionado
    if selected_bairro is None:
        texto_bairro=f''' ### Mostrando dados de **{selected_crime or "todos os tipos de crime"}** para **todos os bairros.**
        '''
        df_filtrado = filtered_df[filtered_df['Local Fato']!='outros']
        
        title_bairro = f"Os 5 bairros de Porto Alegre com maior volume de incidentes"
        stitle_bairro = f"Considerando os incidentes de {selected_crime or 'todos os tipos de crime'}"

        title_tempo = f"Variação no número de incidentes de {selected_crime or 'todos os tipos'} por horário do dia" if selected_tempo == "Hora do Dia" else f"Variação temporal nos incidentes de {selected_crime or 'todos os tipos'} ({selected_tempo})"
        stitle_tempo = f"Média de incidentes por hora considerando todos os bairros" if selected_tempo == "Hora do Dia" else f"Média diária de incidentes considerando todos os bairros"

        title_tipo = f"Número total de incidentes por tipo de crime em todos os bairros"
        stitle_tipo = f" "
    
        title_local = f"O perfil dos locais de crimes nos bairros de Porto Alegre"
        stitle_local = f"Participação por local no total de crimes de todos os bairros"
             
    else:
        texto_bairro = f''' ### Mostrando dados de **{selected_crime or "todos os tipos de crime"}** para **{selected_bairro}**.
          '''
        title_bairro=f"{selected_bairro} em comparação aos bairros com o maior volume de incidentes"
        stitle_bairro=f"Considerando registros de crimes de {selected_crime or 'todos os tipos'}"

    
        title_tempo = f"Variação no número de incidentes de {selected_crime or 'todos os tipos'} por horário do dia" if selected_tempo == "Hora do Dia" else f"Variação temporal nos incidentes de {selected_crime or 'todos os tipos'} ({selected_tempo})"
        stitle_tempo = f"Média de incidentes por hora em {selected_bairro} em comparação com a média de todos os bairros" if selected_tempo == "Hora do Dia" else f"Média diária de {selected_bairro} em comparação com a média de todos os bairros"
    
        title_tipo = f"Perfil de tipos de crime de {selected_bairro} comparado com todos os bairros"
        stitle_tipo = f"Participação por tipo de crime no total de crimes do bairro"
    
        title_local = f"Perfil de locais de crime de {selected_bairro} comparado com todos os bairros"
        stitle_local = f"Participação por local no número total de incidentes de {selected_crime or 'todos os tipos'}"

    df_filtrado = filtered_df[filtered_df['Local Fato']!='outros']
    df_tempo, x_col = agreg_tempo(filtered_df,selected_tempo,selected_bairro)
    fig_tempo = grapher_tempo(df_tempo, x_col, selected_crime,selected_bairro,selected_tempo)
    fig_tipo = grapher_tipo(df_crimes,selected_bairro)
    fig_local = grapher_local(df_filtrado,selected_bairro,selected_crime)
    fig_bairro = grapher_bairro(filtered_df,selected_bairro,selected_crime)
        
    return (
        texto_bairro,
        render_explanation(selected_crime),
        title_bairro,  # Título do gráfico por bairro
        stitle_bairro,  # Subtítulo do gráfico por bairro
        fig_bairro,  # Gráfico por bairro
        title_tempo,
        stitle_tempo,
        fig_tempo,
        title_tipo,
        stitle_tipo,
        fig_tipo,
        title_local,
        stitle_local,
        fig_local,
    )

@app.callback(
    
        Output('mapa-crimes', 'figure'),
        
       
        Input("dp_2", "value"),  # Crime selecionado
        
    
)
def update_map(selected_crime):
    if selected_crime:
        filtered_df = df_crimes[df_crimes["Crime"] == selected_crime]
    else:
        filtered_df = df_crimes
    # Atualizar dados geográficos com a contagem de Incidente_ID únicos por bairro
    incident_counts = (
    filtered_df.groupby('CBairro')['Incidente_ID']
    .nunique()
    .reset_index(name='Incidentes')
    )

# Fazer o merge da contagem com os dados geográficos
    data_geo = data_geo_base.copy()
    data_geo = data_geo.merge(
    incident_counts, 
    how='left', 
    left_on='Bairro', 
    right_on='CBairro'
)

# Preencher valores nulos com zero (para bairros sem incidentes)
    data_geo['Incidentes'] = data_geo['Incidentes'].fillna(0)
    data_geo['location_id'] = data_geo.index
    data_geo = data_geo.to_crs("EPSG:4326")
    # Criar uma cópia da coluna "Incidentes" com o formato desejado
    data_geo["Incidentes_Formatado"] = data_geo["Incidentes"].apply(lambda x: f"{x:,.0f}".replace(",", "."))

    # Adicionando os polígonos ao mapa
    fig_mapa = px.choropleth_mapbox(
        data_geo,
        geojson=data_geo.geometry,
        locations="location_id",
        color="Incidentes",
        color_continuous_scale="Reds",
        mapbox_style="carto-positron",
        zoom=9,
        center={"lat": -30.031831, "lon": -51.228423},
        hover_name="Bairro",  # Nome do bairro
        hover_data={"Incidentes_Formatado": True, "Incidentes": False, "Bairro": False, "location_id": False}  # Mostra o número de incidentes; oculta redundância do nome
    )

    fig_mapa.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0},
    coloraxis_colorbar=dict(
        title="Incidentes",
        tickformat=".",  # Usar separador de milhares
        ticks="outside",  # Opcional, para manter os ticks externos
    ))
    fig_mapa.update_traces(hovertemplate="<b>%{hovertext}</b><br>Incidentes: %{customdata[0]}")
    fig_mapa.update_coloraxes(colorbar_len=0.8)

    
    return fig_mapa

server = app.server  # Esta linha é importante para o Gunicorn

# Rodar o servidor
if __name__ == '__main__':
    app.run_server(debug=False)