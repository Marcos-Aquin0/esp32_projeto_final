// =================================================================
//                    BIBLIOTECAS E DEPENDÊNCIAS
// =================================================================
#include <math.h>             
#include <WiFi.h>             
#include <Wire.h>             
#include <PubSubClient.h>     
#include <Adafruit_AHTX0.h>     
#include <ScioSense_ENS160.h> 

// =================================================================
//                  CONFIGURAÇÕES E VARIÁVEIS GLOBAIS
// =================================================================

//** SwRS-4 **// Default credentials if none received via Serial
const char* default_ssid = "Pereira";
const char* default_password = "toktoklia";

//** SwRS-8 **// MQTT broker configuration
const char *mqtt_broker = "mqtt3.thingspeak.com";
const int mqtt_port = 1883;
const char *client_id = "Hw4bCzIwNRAvEywjKAonCSk";       
const char *mqtt_username = "Hw4bCzIwNRAvEywjKAonCSk"; 
const char *mqtt_password = "muNwStQai/qJtGWkSppvXlAa";   
const char *topic = "channels/2988273/publish";       

//** SwRS-5,6,7 **// Sensor objects and variables
ScioSense_ENS160 ens160(ENS160_I2CADDR_1); 
Adafruit_AHTX0 aht;                      
float tempC = 0;
float humidity = 0;
float pm25 = 0;
int tvoc = 0;
int co = 0;
int aqi = 0;

//** SwRS-7,19,21 **// PM2.5 sensor configuration
const int pin = 12;                      
unsigned long duration = 0;              
unsigned long lowpulseoccupancy = 0;     
float ratio = 0;                         

//** SwRS-1,2 **// Send interval control
unsigned long lastSend = 0;              
const unsigned long sendInterval = 6 * 60 * 1000UL; 
bool enviar = true;                      
bool envioForcado = true;                

//** SwRS-8,9 **// Network clients
WiFiClient espClient;                    
PubSubClient client(espClient);          

// =================================================================
//                          FUNÇÃO SETUP
// =================================================================
void setup() {
  //** SwRS-7 **// Initialize PM2.5 sensor pin
  pinMode(pin, INPUT);         
  Serial.begin(115200);        
  
  //** SwRS-29 **// Initial delay
  delay(1000);                 

  //** SwRS-10 **// Wait for WiFi credentials via Serial
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

  //** SwRS-4 **// Use default credentials if none received
  if (ssid.length() == 0 || password.length() == 0) {
    Serial.println("Tempo esgotado ou dados incompletos. Usando rede WiFi padrão.");
    ssid = default_ssid;
    password = default_password;
  }

  //** SwRS-25,26 **// WiFi connection with status feedback
  Serial.printf("Conectando à rede: %s\n", ssid.c_str());
  WiFi.begin(ssid.c_str(), password.c_str());

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConectado!");
  Serial.printf("IP: %s\n", WiFi.localIP().toString().c_str());

  //** SwRS-8 **// MQTT setup
  client.setServer(mqtt_broker, mqtt_port);
  
  //** SwRS-28 **// Initialize I2C bus
  Wire.begin(16, 17);

  //** SwRS-5,16,30 **// Initialize AHT sensor
  if (!aht.begin()) {
    Serial.println("Sensor AHT não encontrado. Verifique a fiação.");
    while (1) delay(10); 
  }
  Serial.println("Sensor AHT inicializado.");

  //** SwRS-6,17,25 **// Initialize ENS160 sensor
  Serial.print("Inicializando sensor ENS160...");
  if (ens160.begin()) {
      Serial.println(" sucesso!");
      ens160.setMode(ENS160_OPMODE_STD); 
  } else {
      Serial.println(" falhou!");
  }

  //** SwRS-12,13,26 **// ENS160 warmup routine
  if (ens160.available()) {
    Serial.println("Iniciando aquecimento do sensor por 3 minutos para estabilização...");
    unsigned long warmupStartTime = millis();
    while (millis() - warmupStartTime < 180000UL) { 
        //** SwRS-22,23 **// Provide environmental data during warmup
        sensors_event_t humidityEvent, tempEvent;
        aht.getEvent(&humidityEvent, &tempEvent);
        ens160.set_envdata(tempEvent.temperature, humidityEvent.relative_humidity);
        ens160.measure(true);
        delay(5000); 
        Serial.print("."); 
    }
    Serial.println("\nAquecimento concluído. Iniciando medições normais.");
  }
}

// =================================================================
//                        FUNÇÃO DE CONEXÃO MQTT
// =================================================================
//** SwRS-8,9,25 **// MQTT connection and reconnection
void connect_MQTT() {
  while (!client.connected()) {
    Serial.print("Conectando ao broker MQTT: ");
    Serial.println(mqtt_broker);

    if (client.connect(client_id, mqtt_username, mqtt_password)) {
      Serial.println("Conectado ao MQTT!\n");
    } else {
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
//** SwRS-5,6,7,19,20,22,23,24,27 **// Read all sensors
void lerSensores() {
  // Read AHT sensor
  sensors_event_t humidityEvent, tempEvent;
  aht.getEvent(&humidityEvent, &tempEvent);
  tempC = tempEvent.temperature;
  humidity = humidityEvent.relative_humidity;

  // Calculate PM2.5
  ratio = lowpulseoccupancy / (sendInterval * 10.0);
  pm25 = 1.1 * pow(ratio, 3) - 3.8 * pow(ratio, 2) + 520 * ratio + 0.62;
  
  // Read ENS160 if available
  if (ens160.available()) {
    ens160.set_envdata(tempC, humidity);
    ens160.measure(true);
    tvoc = ens160.getTVOC();
    co = ens160.geteCO2();
    aqi = ens160.getAQI();
  } else {
    tvoc = -1;
    co = -1;
    aqi = -1;
  }

  lowpulseoccupancy = 0;
}

// =================================================================
//                      FUNÇÃO DE PUBLICAÇÃO DE DADOS
// =================================================================
//** SwRS-1,3,14,15 **// Publish all data
void publicarTudo() {
  lerSensores(); 

  //** SwRS-15 **// Print values to Serial
  Serial.println("--- Nova Leitura ---");
  Serial.printf("Temperatura: %.2f °C\n", tempC);
  Serial.printf("Umidade: %.2f %%\n", humidity);
  Serial.printf("VOC (TVOC): %d ppb\n", tvoc);
  Serial.printf("CO2 equivalente: %d ppm\n", co);
  Serial.printf("PM2.5: %.2f pcs/0.01cf\n", pm25);
  Serial.printf("AQI: %d\n", aqi);

  //** SwRS-14 **// Format payload string
  String payload = "field1=" + String(tempC, 2) +
                   "&field2=" + String(humidity, 2) +
                   "&field3=" + String(tvoc) +
                   "&field4=" + String(co) +
                   "&field5=" + String(pm25, 2) +
                   "&field6=" + String(aqi);

  // Publish to MQTT
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
//** Main loop implementing multiple requirements **//
void loop() {
  //** SwRS-9,18 **// Maintain MQTT connection
  if (!client.connected()) {
    connect_MQTT();
  }
  client.loop(); 

  //** SwRS-7,21 **// Read PM2.5 sensor pulses
  duration = pulseIn(pin, LOW);
  lowpulseoccupancy += duration;

  //** SwRS-3,11 **// Handle Serial commands
  if (Serial.available()) {
    char c = Serial.read();
    if (c == '1') {
      Serial.println("Envio manual solicitado via Serial.\n");
      publicarTudo();
      while(Serial.available()) Serial.read(); 
    } else {
      enviar = !enviar;
      Serial.println(enviar ? "Envio AUTOMÁTICO ATIVADO\n" : "Envio AUTOMÁTICO DESATIVADO\n");
    }
  }

  //** SwRS-1,2 **// Automatic send logic
  unsigned long now = millis();
  if ((now - lastSend >= sendInterval || envioForcado) && enviar) {
    lastSend = now;          
    envioForcado = false;    
    publicarTudo();          
  }
}
