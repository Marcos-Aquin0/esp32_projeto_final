import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv
import os

load_dotenv()

url = os.getenv("API_URL")

st.set_page_config(layout="wide")
st_autorefresh(interval=10 * 1000, key="refresh")
st.sidebar.title("Menu")

with st.sidebar:
    add_radio = st.radio(
        "Selecione uma opção:",
        ("🌡️ Leitura dos Sensores", "📚 Referência Teórica", "🔔 Alertas", "🛠 Suporte")
    )

def reg_filter (json_data, regex_pattern):
    filtered_data = {}
    for key, value in json_data.items():
        if re.fullmatch(regex_pattern, key): # Use re.fullmatch for exact match of the entire key
            filtered_data[key] = value
    return filtered_data

def convert_datetime (x):
    return datetime.strptime(str(x['created_at']), "%Y-%m-%dT%H:%M:%SZ")

def get_esp32_data():
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()    
        return response.json()
    except Exception as e:
        st.error(f"Erro ao acessar a API: {e}")
        return None

def verificar_intervalo(valor, minimo, maximo):
    """Retorna texto e cor de alerta caso o valor esteja fora do intervalo"""
    if valor < minimo:
        return ("⬇️ Baixo", "inverse")
    elif valor > maximo:
        return ("⬆️ Alto", "inverse")
    return (None, "off")  # Sem destaque

def gerar_metric_texto_colorido(label, valor, unidade, minimo, maximo, recomendacao):
    valor = float(valor)
    fora_do_intervalo = valor < minimo or valor > maximo

    cor = "#dc3545" if fora_do_intervalo else "#198754"  # vermelho ou verde
    tooltip = f'title="{recomendacao}"' if fora_do_intervalo else ""

    html = f"""
    <div style="padding:0.5em;">
        <strong>{label}</strong><br>
        <span style="font-size:1.5em; color:{cor};" {tooltip}>{valor} {unidade}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def alerta_visual(titulo, mensagem, cor="#ffc107"):  # amarelo por padrão
    html = f"""
    <div style="border-left: 8px solid {cor}; background-color: #fff8e1;
                padding: 1em; margin: 1em 0; border-radius: 6px;">
        <h4 style="margin:0; color: {cor}">⚠️ {titulo}</h4>
        <p style="margin:0; color: #444;">{mensagem}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


data = get_esp32_data()
feeds = pd.DataFrame(data['feeds'])
channel = data['channel']
last_data = feeds.loc[feeds['entry_id'].idxmax()]
data_sample = feeds[(feeds['entry_id']<=feeds['entry_id'].max())&(feeds['entry_id']>feeds['entry_id'].max() - 6)]

fields = reg_filter(channel, r".*(field).*")

st.title("🏡 Monitoramento da Qualidade do Ar Interno - ESP32")

feeds['created_at'] = feeds.apply(convert_datetime, axis=1)

if(add_radio == "🌡️ Leitura dos Sensores"):

    st.header("Última leitura")

    if data:
        col1, col2, col3 = st.columns(3)

        with col1:
            gerar_metric_texto_colorido("🌡️ Temperatura", last_data["field1"], "°C", 18, 30,
                                        "Temperatura fora do ideal.")
            gerar_metric_texto_colorido("💧 Umidade", last_data["field2"], "%", 30, 60,
                                        "Umidade inadequada.")

        with col2:
            gerar_metric_texto_colorido("🧪 VOC", last_data["field3"], "ppm", 0, 500,
                                        "Alta concentração de VOCs.")
            gerar_metric_texto_colorido("🟢 eCO₂", last_data["field4"], "ppm", 400, 1000,
                                        "CO₂ elevado.")

        with col3:
            gerar_metric_texto_colorido("🌫️ PM2.5", last_data["field5"], "µg/m³", 0, 35,
                                        "Partículas finas elevadas.")
            gerar_metric_texto_colorido("🏭 AQI", last_data["field6"], "", 4, 5,
                                        "Qualidade do ar ruim.")

        timestamp = datetime.fromisoformat(last_data["created_at"])
        st.caption(f"Última leitura: {timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
    else:
        st.warning("Nenhum dado recebido da API.")

    st.header("Média da última hora")

    if data:
        col1, col2, col3 = st.columns(3)

        # Conversão
        for f in ['field1', 'field2', 'field3', 'field4', 'field5', 'field6']:
            data_sample[f] = data_sample[f].astype(float)

        # Médias
        temp = round(data_sample["field1"].mean(), 2)
        umid = round(data_sample["field2"].mean(), 2)
        voc = round(data_sample["field3"].mean(), 2)
        eco2 = round(data_sample["field4"].mean(), 2)
        pm25 = round(data_sample["field5"].mean(), 2)
        aqi = round(data_sample["field6"].mean(), 2)

        with col1:
           
            gerar_metric_texto_colorido("🌡️ Temperatura", temp, "°C", 18, 30, "Temperatura fora do ideal.")
            if temp < 18 or temp > 30:
                alerta_visual("Alerta Temperatura", "Recomendação para temperatura fora do ideal na ultima hora", "#dc3545")

            gerar_metric_texto_colorido("💧 Umidade", umid, "%", 30, 60, "Umidade inadequada.")
            if umid < 30 or umid > 60:
                alerta_visual("Alerta umidade", "Recomendação para umidade fora do ideal na ultima hora", "#dc3545")

        with col2:
            gerar_metric_texto_colorido("🧪 VOC", voc, "ppm", 0, 500, "Alta concentração de VOCs.")
            if voc > 500:
                alerta_visual("Alerta VOCs", "Recomendação para VOCs fora do ideal na ultima hora", "#dc3545")

            gerar_metric_texto_colorido("🟢 eCO₂", eco2, "ppm", 400, 1000, "CO₂ elevado.")
            if eco2 > 1000:
                alerta_visual("Alerta eCO2", "Recomendação para eCO2 fora do ideal na ultima hora", "#dc3545")

        with col3:
            gerar_metric_texto_colorido("🌫️ PM2.5", pm25, "µg/m³", 0, 35, "Partículas finas elevadas.")
            if pm25 > 35:
                alerta_visual("Alerta PM2.5", "Recomendação para PM2.5 fora do ideal na ultima hora", "#dc3545")

            gerar_metric_texto_colorido("🏭 AQI", aqi, "", 0, 50, "Qualidade do ar ruim.")
            if aqi > 50:
                alerta_visual("Alerta AQI", "Recomendação para AQI fora do ideal na ultima hora", "#dc3545")

        timestamp = datetime.fromisoformat(last_data["created_at"])
        st.caption(f"Última leitura: {timestamp.strftime('%d/%m/%Y %H:%M:%S')}")
    else:
        st.warning("Nenhum dado recebido da API.")

    st.header("Série histórica")

    fields_l = list(fields.items())

    for i in range(0, len(fields), 2):
        cols = st.columns(2)
        for j, (field, field_name) in enumerate(fields_l[i:i+2]):
            with cols[j]:
                st.write(f"Serie histórica - {field_name}")
                st.line_chart(feeds, 
                        x='created_at', 
                        y=field, 
                        height=450, 
                        width=500, 
                        use_container_width=False,
                        x_label='Tempo', 
                        y_label=fields[field]
                        )
    #st.json(channel)
    #st.write(data_sample.rename(columns=fields))

elif(add_radio == "📚 Referência Teórica"):
    st.header("Referência Teórica dos Sensores")
    st.write("Consulte aqui a documentação teórica dos sensores utilizados:")
    st.write("1. **AQI e CO2**: Sensor ENS160")
    st.write("Datasheet: https://www.mouser.com/datasheet/2/1081/SC_001224_DS_1_ENS160_Datasheet_Rev_0_95-2258311.pdf")

    st.subheader("AQI - Índice de Qualidade do Ar")
    tabela_aqi = {
        '#': [1, 2, 3, 4, 5],
        'Classificação': ['Excelente', 'Boa', 'Moderada', 'Ruim', 'Não Saudável'], 
        'Classificação Higiênica': ['Sem objeções', 'Sem objeções relevantes', 'Algumas objeções', 'Maiores objeções', 'Situação não aceitável'], 
        'Recomendação': ['Alvo', 'Ventilação suficiente recomendada', 'Ventilação aumentada recomendada', 'Ventilação intensificada recomendada', 'Usar apenas se inevitável: ventilação intensificada recomendada'],
        'Limite de Exposição': ['sem limite', 'sem limite', '<12 meses', '<1 mês', 'horas'] 
    }
    df = pd.DataFrame(tabela_aqi)

    color_map = {
        'Excelente': 'background-color: #ADD8E6', # Azul Claro (aprox. "light blue")
        'Boa': 'background-color: #90EE90',      # Verde Claro (aprox. "light green")
        'Moderada': 'background-color: #FFD700',   # Dourado (aprox. "gold") - para amarelo
        'Ruim': 'background-color: #FFA500',      # Laranja (aprox. "orange")
        'Não Saudável': 'background-color: #FF6347'  # Tomate (aprox. "tomato") - um vermelho-alaranjado
    }

    text_color_map = {
        'Excelente': 'color: black',
        'Boa': 'color: black',
        'Moderada': 'color: black',
        'Ruim': 'color: black',
        'Não Saudável': 'color: black'
    }

    def color_rows(row):
        """Aplica a cor de fundo e de texto com base na coluna 'Rating'."""
        rating = row['Classificação']
        background_style = color_map.get(rating, '') 
        text_style = text_color_map.get(rating, '')  

        return [f'{background_style}; {text_style}' for _ in row.index]

    st.dataframe(df.style.apply(color_rows, axis=1), hide_index=True)

    st.info("Esta tabela fornece uma classificação da qualidade do ar com recomendações e limites de exposição correspondentes, de acordo com o datasheet do sensor.")

#====
    st.subheader("Tabela de Níveis de eCO2 / CO2 e Qualidade do Ar Interno")

    data_co2 = {
        'eCO₂ / CO₂': ['>1500', '1000 - 1500', '800 - 1000', '600 - 800', '400 - 600'],
        'Classificação': ['Péssimo', 'Ruim', 'Razoável', 'Boa', 'Excelente'], # Tradução de Bad, Poor, Fair, Good, Excellent
        'Comentário / Recomendação': [
            'Ar interno fortemente contaminado / Ventilação necessária',
            'Ar interno contaminado / Ventilação recomendada',
            'Ventilação opcional',
            'Média',
            'Alvo'
        ]
    }
    df = pd.DataFrame(data_co2)

    color_map = {
        'Péssimo': 'background-color: #FF6347',      # Tomate (para o vermelho de "Bad")
        'Ruim': 'background-color: #FFA500',     # Laranja (para o laranja de "Poor")
        'Razoável': 'background-color: #FFD700',  # Dourado (para o amarelo de "Fair")
        'Boa': 'background-color: #90EE90',       # Verde Claro (para o verde de "Good")
        'Excelente': 'background-color: #ADD8E6'  # Azul Claro (para o azul de "Excellent")
    }

    text_color_map = {
        'Péssimo': 'color: white', 
        'Ruim': 'color: black',
        'Razoável': 'color: black',
        'Boa': 'color: black',
        'Excelente': 'color: black'
    }

    def colorir_linhas_co2(linha):
        """Aplica a cor de fundo e de texto com base na coluna 'Classificação'."""
        classificacao = linha['Classificação']
        estilo_fundo = color_map.get(classificacao, '')
        estilo_texto = text_color_map.get(classificacao, '')

        return [f'{estilo_fundo}; {estilo_texto}' for _ in linha.index]

    st.dataframe(df.style.apply(colorir_linhas_co2, axis=1), hide_index=True)

    st.info("Esta tabela mostra os níveis de eCO₂/CO₂ e sua classificação, com comentários e recomendações sobre a qualidade do ar interno.")

    st.write("2. **PM2.5**: Groove-Dust Sensor (PPD42NS)")
    st.write("https://seeeddoc.github.io/Grove-Dust_Sensor/")

    st.write("3. **Temperatura e Umidade**: Sensor AHT21")
    st.write("Datasheet: https://mallimages.ofweek.com/Upload/guige/2025/03/20/6369/606bbf98f38ee.pdf")


elif(add_radio == "🔔 Alertas"):
    st.subheader("Alertas")
    st.write("Adicione seu e-mail para receber notificações quando os níveis ultrapassarem os limites recomendados.")
    email = st.text_input("Digite seu e-mail para receber alertas:", placeholder="example@gmail.com")
    if st.button("Salvar e-mail"):
        if email:
            st.success(f"E-mail {email} salvo com sucesso!")
        else:
            st.error("Por favor, insira um e-mail válido.")
    

elif(add_radio == "🛠 Suporte"):
    st.subheader("Suporte")
    st.write("Em caso de dúvidas ou dificuldades, consulte nossa documentação no repositório: ")
    st.markdown("[https://github.com/gbeloso/esp32-environment]")

    st.write("Ou entre em contato com nosso suporte:")
    st.write("Contato: ✉ example@email.com")
