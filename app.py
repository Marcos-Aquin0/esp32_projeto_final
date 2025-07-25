import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh
from dotenv import load_dotenv
import os
import smtplib 
from email.mime.text import MIMEText 
from email.mime.multipart import MIMEMultipart 

load_dotenv()

# SwRS-33
url = os.getenv("API_URL")

# SwRS-31
st.set_page_config(layout="wide")
# SwRS-32
st_autorefresh(interval=10 * 1000, key="refresh")
st.sidebar.title("Menu")

with st.sidebar:
    # SwRS-31
    add_radio = st.radio(
        "Selecione uma opção:",
        ("🌡️ Leitura dos Sensores", "📚 Referência Teórica", "🔔 Alertas", "🛠 Suporte")
    )

def reg_filter(json_data, regex_pattern):
    filtered_data = {}
    for key, value in json_data.items():
        if re.fullmatch(regex_pattern, key):
            filtered_data[key] = value
    return filtered_data

def convert_datetime(x):
    return datetime.strptime(str(x['created_at']), "%Y-%m-%dT%H:%M:%SZ")

def get_esp32_data():
    try:
        # SwRS-33
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # SwRS-34
        st.error(f"Erro ao acessar a API: {e}")
        return None

def enviar_email_alerta(destinatarios, corpo_html):
    # SwRS-50
    mailtrap_host = os.getenv("host")
    mailtrap_port = os.getenv("port")
    mailtrap_username = os.getenv("username")
    mailtrap_password = os.getenv("password")

    sender_email = "no-reply@alertasesp32.com"

    # SwRS-48
    for receiver_email in destinatarios:
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = "⚠️ Alerta de Qualidade do Ar"
        message.attach(MIMEText(corpo_html, "html"))

        try:
            with smtplib.SMTP(mailtrap_host, mailtrap_port) as server:
                server.starttls()
                server.login(mailtrap_username, mailtrap_password)
                server.sendmail(sender_email, receiver_email, message.as_string())
            st.success(f"Alerta enviado para: {receiver_email} (via Mailtrap)")
        except Exception as e:
            st.error(f"Erro ao enviar e-mail para {receiver_email} (Mailtrap): {e}")


def get_aqi_color(aqi):
    """Retorna a cor baseada no valor do AQI."""
    aqi = float(aqi)
    # SwRS-37, SwRS-39, SwRS-44
    if aqi <= 1: return '#ADD8E6'   # Excelente
    elif aqi <= 2: return '#90EE90'   # Boa
    elif aqi <= 3: return '#FFD700'   # Moderada
    elif aqi <= 4: return '#FFA500'   # Ruim
    else: return '#FF6347'   # Não Saudável

def get_eco2_color(eco2):
    """Retorna a cor baseada no valor do eCO2."""
    eco2 = float(eco2)
    # SwRS-37, SwRS-39, SwRS-44
    if eco2 <= 600: return '#ADD8E6'   # Excelente
    elif eco2 <= 800: return '#90EE90'   # Boa
    elif eco2 <= 1000: return '#FFD700'   # Razoável
    elif eco2 <= 1500: return '#FFA500'   # Ruim
    else: return '#FF6347'   # Péssimo

def gerar_metric_texto_colorido(label, valor, unidade, minimo, maximo, recomendacao, tipo_sensor="default"):
    valor = float(valor)
    fora_do_intervalo = valor < minimo or valor > maximo

    # SwRS-37, SwRS-39
    if tipo_sensor == "aqi": cor = get_aqi_color(valor)
    elif tipo_sensor == "eco2": cor = get_eco2_color(valor)
    else: cor = "#dc3545" if fora_do_intervalo else "#198754"

    tooltip = f'title="{recomendacao}"' if fora_do_intervalo else ""

    html = f"""
    <div style="padding:0.5em;">
        <strong>{label}</strong><br>
        <span style="font-size:1.5em; color:{cor};" {tooltip}>{valor} {unidade}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    return fora_do_intervalo

def alerta_visual(titulo, mensagem, cor="#ffc107"):
    # SwRS-40
    html = f"""
    <div style="border-left: 8px solid {cor}; background-color: #fff8e1;
                padding: 1em; margin: 1em 0; border-radius: 6px;">
        <h4 style="margin:0; color: {cor}">⚠️ {titulo}</h4>
        <p style="margin:0; color: #444;">{mensagem}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


data = get_esp32_data()
if data:
    feeds = pd.DataFrame(data['feeds'])
    channel = data['channel']
    last_data = feeds.loc[feeds['entry_id'].idxmax()]
    data_sample = feeds[(feeds['entry_id'] <= feeds['entry_id'].max()) & (feeds['entry_id'] > feeds['entry_id'].max() - 6)]
    fields = reg_filter(channel, r".*(field).*")

    # SwRS-31
    st.title("🏡 Monitoramento da Qualidade do Ar Interno - ESP32")

    feeds['created_at'] = feeds.apply(convert_datetime, axis=1)
    feeds['created_at'] = feeds['created_at'].dt.tz_localize('UTC')
    # SwRS-35
    utc3_fixed_offset = timezone(timedelta(hours=-3))
    feeds['created_at'] = feeds['created_at'].dt.tz_convert(utc3_fixed_offset)
else:
    # SwRS-34
    st.warning("Nenhum dado recebido da API.")
    st.stop()


if add_radio == "🌡️ Leitura dos Sensores":

    st.header("Última leitura")

    col1, col2, col3 = st.columns(3)

    with col1:
        # SwRS-36, SwRS-37
        gerar_metric_texto_colorido("🌡️ Temperatura", last_data["field1"], "°C", 18, 30, "Temperatura fora do ideal.")
        gerar_metric_texto_colorido("💧 Umidade", last_data["field2"], "%", 30, 60, "Umidade inadequada.")

    with col2:
        # SwRS-36, SwRS-37
        gerar_metric_texto_colorido("🧪 VOC", last_data["field3"], "ppm", 0, 500, "Alta concentração de VOCs.")
        gerar_metric_texto_colorido("🟢 eCO₂", last_data["field4"], "ppm", 400, 1000, "CO₂ elevado.", tipo_sensor="eco2")

    with col3:
        # SwRS-36, SwRS-37
        gerar_metric_texto_colorido("🌫️ PM2.5", last_data["field5"], "µg/m³", 0, 35, "Partículas finas elevadas.")
        gerar_metric_texto_colorido("🏭 AQI", last_data["field6"], "", 1, 5, "Qualidade do ar ruim.", tipo_sensor="aqi")

    timestamp_str = last_data.get("created_at", "N/A")
    if timestamp_str != "N/A":
        try:
            # SwRS-35
            timestamp = pd.to_datetime(timestamp_str).to_pydatetime()
            formatted_timestamp = timestamp.strftime('%d/%m/%Y %H:%M:%S')
            st.caption(f"Última leitura: {formatted_timestamp}")
        except Exception:
            st.caption(f"Última leitura: {timestamp_str}")


    st.header("Média da última hora")

    col1_media, col2_media, col3_media = st.columns(3)

    for f in ['field1', 'field2', 'field3', 'field4', 'field5', 'field6']:
        data_sample[f] = data_sample[f].astype(float)

    temp = round(data_sample["field1"].mean(), 2)
    umid = round(data_sample["field2"].mean(), 2)
    voc = round(data_sample["field3"].mean(), 2)
    eco2 = round(data_sample["field4"].mean(), 2)
    pm25 = round(data_sample["field5"].mean(), 2)
    aqi = round(data_sample["field6"].mean(), 2)

    alertas = []

    with col1_media:
        # SwRS-38, SwRS-40
        if gerar_metric_texto_colorido("🌡️ Temperatura", temp, "°C", 18, 30, "Temperatura fora do ideal."):
            alerta_visual("Alerta Temperatura", f"A média da temperatura ({temp}°C) está fora do ideal.", "#dc3545")
            alertas.append(f"<li>Temperatura: <b>{temp}°C</b> (Ideal: 18-30°C)</li>")

        # SwRS-38, SwRS-40
        if gerar_metric_texto_colorido("💧 Umidade", umid, "%", 30, 60, "Umidade inadequada."):
            alerta_visual("Alerta Umidade", f"A média da umidade ({umid}%) está fora do ideal.", "#dc3545")
            alertas.append(f"<li>Umidade: <b>{umid}%</b> (Ideal: 30-60%)</li>")

    with col2_media:
        # SwRS-38, SwRS-40
        if gerar_metric_texto_colorido("🧪 VOC", voc, "ppm", 0, 500, "Alta concentração de VOCs."):
            alerta_visual("Alerta VOCs", f"A média de VOCs ({voc} ppm) está alta.", "#dc3545")
            alertas.append(f"<li>VOC: <b>{voc} ppm</b> (Ideal: < 500 ppm)</li>")

        # SwRS-38, SwRS-39, SwRS-40
        if gerar_metric_texto_colorido("🟢 eCO₂", eco2, "ppm", 400, 1000, "CO₂ elevado.", tipo_sensor="eco2"):
            cor_alerta = get_eco2_color(eco2)
            alerta_visual("Alerta eCO2", f"A média de eCO2 ({eco2} ppm) está elevada.", cor_alerta)
            alertas.append(f"<li>eCO2: <b>{eco2} ppm</b> (Ideal: 400-1000 ppm)</li>")

    with col3_media:
        # SwRS-38, SwRS-40
        if gerar_metric_texto_colorido("🌫️ PM2.5", pm25, "µg/m³", 0, 35, "Partículas finas elevadas."):
            alerta_visual("Alerta PM2.5", f"A média de PM2.5 ({pm25} µg/m³) está alta.", "#dc3545")
            alertas.append(f"<li>PM2.5: <b>{pm25} µg/m³</b> (Ideal: < 35 µg/m³)</li>")

        # SwRS-38, SwRS-39, SwRS-40
        if gerar_metric_texto_colorido("🏭 AQI", aqi, "", 1, 3, "Qualidade do ar ruim.", tipo_sensor="aqi"):
            cor_alerta = get_aqi_color(aqi)
            alerta_visual("Alerta AQI", f"A média do AQI ({aqi}) indica qualidade do ar ruim.", cor_alerta)
            alertas.append(f"<li>AQI: <b>{aqi}</b> (Ideal: 1-3)</li>")

    # SwRS-48
    if alertas and "emails_alerta" in st.session_state and st.session_state.emails_alerta:
        destinatarios = [email.strip() for email in st.session_state.emails_alerta.split(',') if email.strip()]
        if destinatarios:
            corpo_html = "<h3>⚠️ Alerta de Qualidade do Ar</h3><p>Os seguintes sensores apresentaram leituras fora do ideal na última hora:</p><ul>" + "".join(alertas) + "</ul><p>Atenciosamente,<br>Sistema de Monitoramento</p>"
            # enviar_email_alerta(destinatarios, corpo_html)


    st.header("Série histórica")
    for field in fields.keys():
        feeds[field] = pd.to_numeric(feeds[field], errors='coerce')

    # SwRS-41
    for i in range(0, len(fields), 2):
        cols = st.columns(2)
        for j, (field, field_name) in enumerate(list(fields.items())[i:i+2]):
            with cols[j]:
                st.write(f"Serie histórica - {field_name}")
                st.line_chart(feeds,
                                x='created_at',
                                y=field,
                                height=450,
                                width=500,
                                use_container_width=False,
                                x_label='Tempo',
                                y_label=field_name)

elif add_radio == "📚 Referência Teórica":
    # SwRS-42
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
    # SwRS-43
    df_aqi = pd.DataFrame(tabela_aqi)

    color_map_aqi = {
        'Excelente': 'background-color: #ADD8E6',
        'Boa': 'background-color: #90EE90',
        'Moderada': 'background-color: #FFD700',
        'Ruim': 'background-color: #FFA500',
        'Não Saudável': 'background-color: #FF6347'
    }

    def color_rows_aqi(row):
        rating = row['Classificação']
        style = color_map_aqi.get(rating, '')
        return [f'{style}; color: black' for _ in row.index]

    # SwRS-44
    st.dataframe(df_aqi.style.apply(color_rows_aqi, axis=1), hide_index=True)

    st.subheader("Tabela de Níveis de eCO2 / CO2 e Qualidade do Ar Interno")
    data_co2 = {
        'eCO₂ / CO₂ (ppm)': ['400 - 600', '600 - 800', '800 - 1000', '1000 - 1500', '>1500'],
        'Classificação': ['Excelente', 'Boa', 'Razoável', 'Ruim', 'Péssimo'],
        'Comentário / Recomendação': [
            'Alvo',
            'Média',
            'Ventilação opcional',
            'Ar interno contaminado / Ventilação recomendada',
            'Ar interno fortemente contaminado / Ventilação necessária'
        ]
    }
    # SwRS-43
    df_co2 = pd.DataFrame(data_co2)

    color_map_co2 = {
        'Excelente': 'background-color: #ADD8E6',
        'Boa': 'background-color: #90EE90',
        'Razoável': 'background-color: #FFD700',
        'Ruim': 'background-color: #FFA500',
        'Péssimo': 'background-color: #FF6347'
    }

    def color_rows_co2(row):
        rating = row['Classificação']
        style = color_map_co2.get(rating, '')
        text_color = 'white' if rating == 'Péssimo' else 'black'
        return [f'{style}; color: {text_color}' for _ in row.index]

    # SwRS-44
    st.dataframe(df_co2.style.apply(color_rows_co2, axis=1), hide_index=True)

    # SwRS-42
    st.write("2. **PM2.5**: Groove-Dust Sensor (PPD42NS)")
    st.write("https://seeeddoc.github.io/Grove-Dust_Sensor/")
    st.write("3. **Temperatura e Umidade**: Sensor AHT21")
    st.write("Datasheet: https://mallimages.ofweek.com/Upload/guige/2025/03/20/6369/606bbf98f38ee.pdf")


elif add_radio == "🔔 Alertas":
    # SwRS-45
    st.subheader("Alertas por E-mail")
    st.write("Adicione e-mails (separados por vírgula) para receber notificações. Esses e-mails serão enviados para sua caixa de entrada virtual do Mailtrap para fins de teste.")

    # SwRS-47
    if "emails_alerta" not in st.session_state:
        st.session_state.emails_alerta = ""

    # SwRS-45
    emails_input = st.text_area("Digite os e-mails para receber alertas:",
                                 value=st.session_state.emails_alerta,
                                 placeholder="email1@exemplo.com, email2@exemplo.com")

    if st.button("Salvar E-mails"):
        if emails_input:
            # SwRS-46
            lista_emails = [email.strip() for email in emails_input.split(',') if email.strip()]
            st.session_state.emails_alerta = ", ".join(lista_emails)
            st.success(f"E-mails salvos com sucesso!")
        else:
            st.session_state.emails_alerta = ""
            # SwRS-46
            st.error("Por favor, insira e-mails válidos.")

elif add_radio == "🛠 Suporte":
    # SwRS-49
    st.subheader("Suporte")
    st.write("Em caso de dúvidas ou dificuldades, consulte nossa documentação no repositório:")
    st.write("Ou entre em contato com nosso suporte:")
    st.write("Contato: ✉ example@email.com")