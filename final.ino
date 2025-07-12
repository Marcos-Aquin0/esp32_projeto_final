// =================================================================
//                    BIBLIOTECAS E DEPENDÊNCIAS
// =================================================================
// Inclusão das bibliotecas necessárias para o funcionamento do projeto.
#include <math.h>             // Para funções matemáticas como pow() no cálculo do PM2.5.
#include <WiFi.h>             // Para gerenciar a conexão Wi-Fi do ESP32.
#include <Wire.h>             // Para comunicação no barramento I2C, usado pelos sensores.
#include <PubSubClient.h>     // Cliente MQTT para enviar dados para plataformas de IoT.
#include <Adafruit_AHTX0.h>     // Biblioteca para o sensor de temperatura e umidade AHT.
#include <ScioSense_ENS160.h> // Biblioteca para o sensor de qualidade do ar (CO2, TVOC) ENS160.

// =================================================================
//                  CONFIGURAÇÕES E VARIÁVEIS GLOBAIS
// =================================================================

// --- WiFi & MQTT ---
String ssid;                  // Variável para armazenar o nome da rede Wi-Fi (SSID).
String password;              // Variável para armazenar a senha da rede Wi-Fi.

// Credenciais padrão, caso nenhuma seja fornecida via Serial.
const char* default_ssid = "Pereira";
const char* default_password = "toktoklia";

// Configurações do Broker MQTT (ThingSpeak).
const char *mqtt_broker = "mqtt3.thingspeak.com";
const int mqtt_port = 1883;
const char *client_id = "Hw4bCzIwNRAvEywjKAonCSk";       // ID único do cliente para o broker.
const char *mqtt_username = "Hw4bCzIwNRAvEywjKAonCSk"; // Usuário para autenticação no broker.
const char *mqtt_password = "muNwStQai/qJtGWkSppvXlAa";   // Senha para autenticação no broker.
const char *topic = "channels/2988273/publish";       // Tópico onde os dados serão publicados.

// --- Sensores ---
// Cria os objetos que representarão os sensores físicos.
ScioSense_ENS160 ens160(ENS160_I2CADDR_1); // Objeto para o sensor ENS160.
Adafruit_AHTX0 aht;                      // Objeto para o sensor AHT.

// Variáveis para armazenar os dados lidos dos sensores.
float tempC = 0;
float humidity = 0;
float pm25 = 0;
int tvoc = 0;
int co = 0;
int aqi = 0;

// --- PM2.5 ---
const int pin = 12;                      // Pino digital onde o sensor de PM2.5 está conectado.
unsigned long duration = 0;              // Armazena a duração de um pulso do sensor.
unsigned long lowpulseoccupancy = 0;     // Acumula o tempo total que o pino ficou em nível baixo.
float ratio = 0;                         // Proporção do tempo em nível baixo, usada no cálculo.

// --- Controle de Envio ---
unsigned long lastSend = 0;              // Armazena o tempo (em ms) do último envio de dados.
const unsigned long sendInterval = 6 * 60 * 1000UL; // MODIFICADO: Intervalo de envio de 6 minutos.
bool enviar = true;                      // Flag para habilitar/desabilitar o envio automático.
bool envioForcado = true;                // Flag para forçar o envio na primeira execução do loop.

// --- Clientes de Rede ---
WiFiClient espClient;                    // Cliente Wi-Fi.
PubSubClient client(espClient);          // Cliente MQTT, que utiliza a conexão Wi-Fi.

// =================================================================
//                          FUNÇÃO SETUP
// =================================================================
// Esta função é executada uma única vez, quando o dispositivo liga.
void setup() {
  pinMode(pin, INPUT);         // Configura o pino do sensor de poeira como entrada.
  Serial.begin(115200);        // Inicia a comunicação serial para depuração.
  delay(1000);                 // Pequena pausa para estabilização.

  // Permite que o usuário insira credenciais de Wi-Fi pela Serial por 10 segundos.
  Serial.println("Aguardando entrada de SSID e senha por 10 segundos...");
  unsigned long startTime = millis();

  while (millis() - startTime < 10000) {
    if (Serial.available()) {
      ssid = Serial.readStringUntil('\n');
      ssid.trim();
      Serial.println("SSID recebido. Agora digite a senha:");
      while (!Serial.available()) delay(100);
      password = Serial.readStringUntil('\n');
      password.trim();
      break;
    }
    delay(100);
  }

  // Se nenhuma credencial foi inserida, usa os valores padrão.
  if (ssid.length() == 0 || password.length() == 0) {
    Serial.println("Tempo esgotado ou dados incompletos. Usando rede WiFi padrão.");
    ssid = default_ssid;
    password = default_password;
  }

  // Inicia a conexão com a rede Wi-Fi.
  Serial.printf("Conectando à rede: %s\n", ssid.c_str());
  WiFi.begin(ssid.c_str(), password.c_str());

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado!");
  Serial.printf("IP: %s\n", WiFi.localIP().toString().c_str());

  // Configura o servidor MQTT.
  client.setServer(mqtt_broker, mqtt_port);
  
  // Inicia o barramento I2C nos pinos 16 (SDA) e 17 (SCL).
  Wire.begin(16, 17);

  // Inicializa o sensor de temperatura e umidade.
  if (!aht.begin()) {
    Serial.println("Sensor AHT não encontrado. Verifique a fiação.");
    while (1) delay(10); // Trava a execução se o sensor não for encontrado.
  }
  Serial.println("Sensor AHT inicializado.");

  // Inicializa o sensor de qualidade do ar.
  Serial.print("Inicializando sensor ENS160...");
  if (ens160.begin()) {
      Serial.println(" sucesso!");
      ens160.setMode(ENS160_OPMODE_STD); // Define o modo de operação padrão.
  } else {
      Serial.println(" falhou!");
  }

  // --- MODIFICAÇÃO: ROTINA DE AQUECIMENTO DO SENSOR ---
  // Sensores como o ENS160 precisam de um tempo para aquecer e estabilizar.
  if (ens160.available()) {
    Serial.println("Iniciando aquecimento do sensor por 3 minutos para estabilização...");
    unsigned long warmupStartTime = millis();
    while (millis() - warmupStartTime < 180000UL) { // 3 minutos = 180000 ms
        // Forçar leituras durante o aquecimento ajuda o sensor a se estabilizar mais rápido.
        sensors_event_t humidityEvent, tempEvent;
        aht.getEvent(&humidityEvent, &tempEvent);
        // Fornece dados de ambiente para compensação interna do sensor.
        ens160.set_envdata(tempEvent.temperature, humidityEvent.relative_humidity);
        ens160.measure(true);
        delay(5000); // Faz uma leitura a cada 5 segundos.
        Serial.print("."); // Feedback visual para o usuário.
    }
    Serial.println("\nAquecimento concluído. Iniciando medições normais.");
  }
}

// =================================================================
//                        FUNÇÃO DE CONEXÃO MQTT
// =================================================================
// Responsável por conectar e reconectar ao broker MQTT.
void connect_MQTT() {
  while (!client.connected()) {
    Serial.print("Conectando ao broker MQTT: ");
    Serial.println(mqtt_broker);

    if (client.connect(client_id, mqtt_username, mqtt_password)) {
      Serial.println("Conectado ao MQTT!\n");
    } else {
      // Se a conexão falhar, imprime o código de erro para diagnóstico.
      int state = client.state();
      Serial.printf("Falha na conexão MQTT, estado: %d -> ", state);
      switch (state) {
        case -4: Serial.println("MQTT_CONNECTION_TIMEOUT"); break;
        case -3: Serial.println("MQTT_CONNECTION_LOST"); break;
        case -2: Serial.println("MQTT_CONNECT_FAILED"); break;
        case -1: Serial.println("MQTT_DISCONNECTED"); break;
        case  0: Serial.println("MQTT_CONNECTED"); break;
        case  1: Serial.println("MQTT_CONNECT_BAD_PROTOCOL"); break;
        case  2: Serial.println("MQTT_CONNECT_BAD_CLIENT_ID"); break;
        case  3: Serial.println("MQTT_CONNECT_UNAVAILABLE"); break;
        case  4: Serial.println("MQTT_CONNECT_BAD_CREDENTIALS"); break;
        case  5: Serial.println("MQTT_CONNECT_UNAUTHORIZED"); break;
        default: Serial.println("Erro desconhecido"); break;
      }
      Serial.println("Tentando novamente em 2 segundos...");
      delay(2000);
    }
  }
}

// =================================================================
//                       FUNÇÃO DE LEITURA DOS SENSORES
// =================================================================
// Centraliza a coleta de dados de todos os sensores.
void lerSensores() {
  // Lê temperatura e umidade do sensor AHT.
  sensors_event_t humidityEvent, tempEvent;
  aht.getEvent(&humidityEvent, &tempEvent);
  tempC = tempEvent.temperature;
  humidity = humidityEvent.relative_humidity;

  // Calcula a concentração de PM2.5 com base no tempo acumulado de pulso baixo.
  ratio = lowpulseoccupancy / (sendInterval * 10.0);
  pm25 = 1.1 * pow(ratio, 3) - 3.8 * pow(ratio, 2) + 520 * ratio + 0.62;
  
  // Se o sensor ENS160 estiver disponível, faz a leitura.
  if (ens160.available()) {
    // ESSENCIAL: Fornece os dados de temperatura e umidade para o sensor ENS160
    // realizar a compensação e garantir leituras precisas.
    ens160.set_envdata(tempC, humidity);
    ens160.measure(true);
    tvoc = ens160.getTVOC();
    co = ens160.geteCO2();
    aqi = ens160.getAQI();
  } else {
    // Se o sensor falhar, atribui valores de erro.
    tvoc = -1;
    co = -1;
    aqi = -1;
  }

  // Zera o acumulador de pulso do PM2.5 para iniciar uma nova medição no próximo ciclo.
  lowpulseoccupancy = 0;
}

// =================================================================
//                      FUNÇÃO DE PUBLICAÇÃO DE DADOS
// =================================================================
// Formata e envia os dados para o ThingSpeak via MQTT.
void publicarTudo() {
  lerSensores(); // Primeiro, obtém as leituras mais recentes.

  // Imprime os valores no monitor serial para depuração local.
  Serial.println("--- Nova Leitura ---");
  Serial.printf("Temperatura: %.2f °C\n", tempC);
  Serial.printf("Umidade: %.2f %%\n", humidity);
  Serial.printf("VOC (TVOC): %d ppb\n", tvoc);
  Serial.printf("CO2 equivalente: %d ppm\n", co);
  Serial.printf("PM2.5: %.2f pcs/0.01cf\n", pm25);
  Serial.printf("AQI: %d\n", aqi);

  // Monta a string de 'payload' no formato exigido pelo ThingSpeak:
  // "field1=VALOR1&field2=VALOR2&..."
  String payload = "field1=" + String(tempC, 2) +
                   "&field2=" + String(humidity, 2) +
                   "&field3=" + String(tvoc) +
                   "&field4=" + String(co) +
                   "&field5=" + String(pm25, 2) + // Arredonda o valor do PM2.5 para 2 casas decimais.
                   "&field6=" + String(aqi);

  // Se o cliente MQTT estiver conectado, publica a mensagem.
  if (client.connected()) {
    if (client.publish(topic, payload.c_str())) {
      Serial.println("Dados enviados com sucesso para o ThingSpeak!\n");
    } else {
      Serial.println("Falha ao publicar no MQTT.\n");
    }
  }
}

// =================================================================
//                           FUNÇÃO LOOP
// =================================================================
// Este é o ciclo principal que se repete indefinidamente.
void loop() {
  // Garante que o cliente MQTT esteja sempre conectado.
  if (!client.connected()) {
    connect_MQTT();
  }
  client.loop(); // Essencial para manter a conexão MQTT e processar mensagens.

  // Acumula continuamente a duração dos pulsos baixos do sensor de poeira.
  duration = pulseIn(pin, LOW);
  lowpulseoccupancy += duration;

  // Verifica se há um comando vindo da porta Serial.
  if (Serial.available()) {
    char c = Serial.read();
    if (c == '1') {
      // Se o caractere '1' for recebido, força um envio imediato.
      Serial.println("Envio manual solicitado via Serial.\n");
      publicarTudo();
      while(Serial.available()) Serial.read(); // Limpa o buffer serial.
    } else {
      // Qualquer outro caractere alterna o envio automático.
      enviar = !enviar;
      Serial.println(enviar ? "Envio AUTOMÁTICO ATIVADO\n" : "Envio AUTOMÁTICO DESATIVADO\n");
    }
  }

  // Lógica de tempo para o envio automático.
  unsigned long now = millis();
  if ((now - lastSend >= sendInterval || envioForcado) && enviar) {
    lastSend = now;          // Atualiza o tempo do último envio.
    envioForcado = false;    // Desativa o envio forçado após a primeira vez.
    publicarTudo();          // Chama a função para ler e publicar os dados.
  }
}