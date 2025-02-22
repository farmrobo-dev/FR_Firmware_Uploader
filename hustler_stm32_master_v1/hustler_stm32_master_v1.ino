#include "sbus.h"
#include <stdint.h>
#include <ezButton.h>
#include "Filter.h"
#include <Wire.h>
#include "MCP4725.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <HardwareSerial.h>
#include "STM32_CAN.h"

String ROBOT_ID = "FRV004202412";
String robot_version = "1.0";    // 1.0
String software_version = "1.0"; // 1.0
#define is_blade 1
#define is_tyne 1
#define is_rotovator 1
#define is_boomsprayer 1
#define is_mistblower 0
#define is_trailer 0

#define DEBUG 0
#define ROW_KEEPING 0
bool IS_MOTORS_REVERSED = 1;
#define IS_THIS_SPEED_BOT 0
#define HAS_PTO_DAC 1 // if DAC 1 if PWM 0

#if IS_THIS_SPEED_BOT == 1
// #define spd_ratio 0.75
#define spd_ratio 1
#else
#define spd_ratio 1
#endif

int set_depth = 30;  // depth control depth
#define dc_amps 40   // depth control amps
#define dc_time 1000 // depth control time

#if DEBUG == 1
#define debug(x) Serial.print(x)
#define debugln(x) Serial.println(x)
#else
#define debug(x)
#define debugln(x)
#endif

// transmitter channels SIYI
#define TH_CH 3
#define ST_CH 1
#define ACT_CH 6
#define ENA_CH 8
#define SPD_CH 5
#define PTO_CH 11
#define RK_CH 10
#define DC_CH 9
#define TOOL_CH 7
#define HORN_CH 13

#if IS_MOTORS_REVERSED == 1
#define MotorRpwm PE9
#define MotorLpwm PE11
#else
#define MotorLpwm PE9
#define MotorRpwm PE11
#endif
#define LIGHT_RELAY PD6
#define PANEL_FAN_RELAY PD4
#define BOTTOM_FAN_RELAY PD5
#define act_rpwm PE13
#define act_lpwm PE14
#define TEMP1_PIN PC3
#define TEMP2_PIN PC0
#define TEMP3_PIN PF3

#define SBUS_RX PD2
#define SBUS_TX PC12

#define TELEM_RX PC11
#define TELEM_TX PC10

#define TOOL_RX PG9
#define TOOL_TX PG14

#define SDA_PIN PF0
#define SCL_PIN PF1

// #define LTE_RX PG9
// #define LTE_TX PG14

// #define Winch_PWM1 PG9
// #define Winch_PWM2 PG14

#define CURRENT_SENSOR_PIN_1 PF7
#define CURRENT_SENSOR_PIN_2 PF9
#define ActuatorFB_PIN PF8
#define BUMPER_SENSOR_PIN PF5

#define HORN_RELAY PD3

// #if HAS_PTO_DAC == 1
MCP4725 PTO_DAC(0x60);
// #else
#define PTO_PWM_PIN PA0
// #endif

int left_speed = 0, right_speed = 0, max_spd = 60;
int targetThrottle = 0, currentThrottle = 0, steer = 0, enable_switch = 0, speed = 0, actuator = 0;
bool lane_follow = 0, cruise_stopped = 0;
bool bumper_alarm = 1;
double prev_looptime = millis(), current_lasttime, lastLoggedTime, last_bumper_hit, last_sbus_data;
String ErrorMessage = "stop";
int dc_on = 0, rk_on = 0, current_rotavator_speed = 0, tool_on_off_button = 0;

// ###### Depth control #########
const int mini_range = 130; // Minimum resistance value from the potentiometer
const int max_range = 390;  // Maximum resistance value from the potentiometer
int current_depth = 0;
bool over_depth = 0;
int ActuatorFB = 0;
bool act_up_called = false;
unsigned long act_up_start_time = 0;
// timer to keep track of the duration the current has been above the threshold
static unsigned long currentAboveThresholdDuration = 0;
// ###### Depth control #########

float current1 = 0, current2 = 0;
float temp1, temp2, temp3;
int temp1_count, temp2_count, lights_count;

int blMotorSpeedInRPMCh1, blMotorSpeedInRPMCh2;
int internalVoltagesVInt, internalVoltagesMV, DriverSupplyVoltage, caseInternalTempMCU, caseInternalTempCh1, caseInternalTempCh2;
uint8_t statusFlags, faultFlags, RuntimeStatusFlags;
float BMSVoltage, BMScurrent;
int RSOC, NTC1Temp, NTC2Temp, NTC3Temp, NTC4Temp, NTC5Temp; //, NTC6Temp;

int remainingCapacity;
int fullCapacity;
int cycleTimes;
int balanceStatus;
int protectionStatus;
int FETControlStatus;
// String productionDate;
// int softwareVersion;
// int seriesOfBattery;
// int NTCNumbers;
int cellVoltages[16];

uint16_t critical_data_IDs[] = {0x100, 0x101, 0x105, 0x106};
uint16_t normal_data_IDs[] = {0x102, 0x103, 0x107, 0x108, 0x109, 0x10A, 0x10B, 0x10C}; // 0x104, 0x10D, 0x10E, 0x10F, 0x110};
int BMScurrentIDIndex = 0;
unsigned long BMSlastSent = 0;

// telemetry data processing
const int txDataSize = 16; // Size of the data array to send
const int rxDataSize = 10; // Size of the data array to receive
int dataToSend[txDataSize];
int dataReceived[rxDataSize];
bool basic_data_req = 0, tools_halt = 1;
int CAN_sensor_status[2] = {0, 0}; // Driver CAN, BMS CAN ; 0 = Not OK, 1 = OK

unsigned long lastCriticalDataTime = 0;
unsigned long lastNormalDataTime = 0;

String mainReceivedString; // Main received string
bool newTelemetryData = false;

int DL_message_ID = 0;
int looptime;
String telem_Timestamp;
int messageID, ControlMode, PathMode, Lights, App_Emergency, ToolType, Tool_On_Off, telem_dummy2;
int tooldata[17];

OneWire tempSensor_1(TEMP1_PIN);
OneWire tempSensor_2(TEMP2_PIN);
// OneWire tempSensor_3(TEMP3_PIN);

DallasTemperature temp1_sensor(&tempSensor_1);
DallasTemperature temp2_sensor(&tempSensor_2);
// DallasTemperature temp3_sensor(&tempSensor_3);

ExponentialFilter<long> Pot_Filter(10, 0);
ezButton BUMPER_SENSOR(BUMPER_SENSOR_PIN);

HardwareSerial sbus_serial(SBUS_RX, SBUS_TX);
HardwareSerial telemetry_serial(TELEM_RX, TELEM_TX);
HardwareSerial tool_serial(TOOL_RX, TOOL_TX);

bfs::SbusRx sbus_rx(&sbus_serial);
bfs::SbusData sbus_data;

STM32_CAN Can(CAN1, ALT_2); // Using PD0/1 pins for CAN1
static CAN_message_t CAN_RX_msg;

// SIYI transmitter sbus mapping
int readChannel(byte channelInput, int minLimit, int maxLimit, int defaultValue)
{
  uint16_t ch = sbus_data.ch[channelInput - 1];
  if (ch < 272)
    return defaultValue;
  return map(ch, 272, 1712, minLimit, maxLimit);
}

void debugging()
{
  debug(" Current mA ");
  debug(BMScurrent);
  debug(" Current2 mA ");
  debug(0);
  debug(" Pot: ");
  debug(ActuatorFB);
  debug(" th : ");
  debug(currentThrottle);
  debug(" T1: ");
  debug(temp1);
  debug(" T2: ");
  debug(temp2);
  debug(" T3: ");
  debug(temp3);
  debug(" st: ");
  debug(steer);
  debug(" DriverSupplyVoltage: ");
  debug(DriverSupplyVoltage);
  debug(" caseInternalTempMCU: ");
  debug(caseInternalTempMCU);
  debug(" bumper: ");
  debug(bumper_alarm);
  debug(" App_Emergency: ");
  debug(App_Emergency);
  debug(" ErrorMessage: ");
  debug(ErrorMessage);
  debug(" looptime: ");
  debug(looptime);
}

void depth_control_current()
{
  // Check if the current is above the threshold
  if (BMScurrent > dc_amps)
  {
    // Increase the duration if current is above the threshold
    currentAboveThresholdDuration += millis() - current_lasttime;
  }
  else
  {
    currentAboveThresholdDuration = 0;
  }
  // Check if the duration is more than 2 seconds
  if (currentAboveThresholdDuration >= dc_time && act_up_called == false)
  {
    // Move actuator up

    act_up_called = true;
    act_up_start_time = millis(); // Record the start time
    current_depth = set_depth + 5;
  }
  else if (currentAboveThresholdDuration >= 1500 && act_up_called == true)
  {
    current_depth += 10;
    over_depth = 1;
  }
  // Reset the duration if current falls below the threshold

  if (act_up_called)
  {
    act_move_to(current_depth);
    // Calculate the time difference
    unsigned long current_time = millis();
    unsigned long elapsed_time = current_time - act_up_start_time;

    // Check if 0.8/1.2 seconds have passed
    if (elapsed_time >= 800)
    {
      // Reset the flag and call the read_actuator function
      act_up_called = false;
      //   read_actuator();
      over_depth = 0;
      act_move_to(set_depth);
    }
  }
  else
  {
    // read_actuator();
    over_depth = 0;
    act_move_to(set_depth);
  }
  // }
  current_lasttime = millis();
}

void act_move_to(int target_pos)
{
  // debug("act moving to ");
  // debugln(target_pos);
  // ActuatorFB = (analogRead(ActuatorFB_PIN) / 10) * 10;
  // Pot_Filter.Filter(ActuatorFB);
  // ActuatorFB = Pot_Filter.Current();
  // ActuatorFB = map(ActuatorFB, mini_range, max_range, 100, 0);

  if (ActuatorFB >= (target_pos + 2))
  {
    if (abs(ActuatorFB - (target_pos + 2)) < 3)
    {
      act_stop();
    }
    else
    {
      act_up();
    }
  }
  else if (ActuatorFB <= (target_pos - 2))
  {
    if (abs(ActuatorFB - (target_pos - 2)) < 3)
    {
      act_stop();
    }
    else
    {
      act_down();
    }
  }
  else
  {
    act_stop();
  }
}

void depth_control()
{
  dc_on = readChannel(DC_CH, -100, 100, 0);
  if (dc_on < 50)
  {
    ErrorMessage = "manual actuator control";
    act_stop();
  }
  else
  {
    ErrorMessage = "depth control on";
    if (ToolType == 1)
    {
      switch (tooldata[5]) // blade
      {
      case 1:
        set_depth = 30;
        break;
      case 2:
        set_depth = 20;
        break;
      case 3:
        set_depth = 10;
        break;
      default:
        set_depth = 30;
        break;
      }
    }
    depth_control_current();
  }
}
void calc_throttle_steer()
{

  targetThrottle = readChannel(TH_CH, -60, 60, 0);
  if (lane_follow == 1)
  {
    if (abs(targetThrottle) > 10)
    {
      cruise_stopped = 1;
    }

    if (cruise_stopped == 0)
    {
      if (ToolType == 3 | ToolType == 5)
      {
        targetThrottle = 23 * spd_ratio; // for rotavator / mistblower
      }
      else
      {
        targetThrottle = 30 * spd_ratio; // for inplant
      }
    }
  }
  else
  {
    cruise_stopped = 0;
    if (ROW_KEEPING == 1)
    {
      check_RK();
    }
  }
  if (PathMode == 2)
  {
    targetThrottle = constrain(targetThrottle, -max_spd, max_spd);
  }
  else
  {
    targetThrottle = constrain(targetThrottle, -max_spd, max_spd) * spd_ratio;
  }

  steer = readChannel(ST_CH, -20, 20, 0);

  if (over_depth == 1 || (dc_on > 50))
  {
    targetThrottle = constrain(targetThrottle, -30, 30) * spd_ratio;
  }
  if (bumper_alarm == 0)
  {
    if (targetThrottle > 0)
    {
      targetThrottle = 0;
    }
    last_bumper_hit = millis();
  }
  else
  {
    if ((millis() - last_bumper_hit) < 5000)
    {
      if (targetThrottle > 0)
      {
        targetThrottle = 0;
      }
    }
  }

  if (abs(targetThrottle) <= 5)
  {
    targetThrottle = 0;
  }
  if (abs(steer) <= 5)
  {
    steer = 0;
  }

  if (abs(steer) > 5)
  {
    if (IS_THIS_SPEED_BOT == 0)
    {
      targetThrottle = constrain(targetThrottle, -40, 40);
    }
  }

  calculate_currentThrottle();
}
void calculate_currentThrottle()
{
  if (targetThrottle == 0 || currentThrottle == 0)
  {
    currentThrottle = targetThrottle;
  }
  else if ((currentThrottle > 0 && targetThrottle < 0) || (currentThrottle < 0 && targetThrottle > 0))
  {
    currentThrottle = 0;
  }
  else
  {
    // Gradually adjust throttle
    if (targetThrottle > currentThrottle)
    {
      currentThrottle += min(targetThrottle - currentThrottle, 1); // Adjust by +5 or remaining difference if less
    }
    else if (targetThrottle < currentThrottle)
    {
      currentThrottle -= min(currentThrottle - targetThrottle, 1); // Adjust by -5 or remaining difference if less
    }
  }
}
void updateMotorSpeeds(int linear_speed, int turnRate)
{

  int differential = map(abs(turnRate), 0, 60, 0, abs(linear_speed));
  int left_speed = linear_speed;
  int right_speed = linear_speed;

  if (turnRate > 0)
  {
    if (linear_speed > 0)
    {
      right_speed -= differential * 2;
    }
    else
    {
      left_speed += differential * 2;
    }
  }
  else if (turnRate < 0)
  {
    if (linear_speed > 0)
    {
      left_speed -= differential * 2;
    }
    else
    {
      right_speed += differential * 2;
    }
  }
  if (abs(turnRate) > 0)
  {
    if (abs(left_speed) > 0 && abs(left_speed) < 10)
    {
      if (left_speed > 0)
      {
        left_speed = 10;
      }
      if (left_speed < 0)
      {
        left_speed = -10;
      }
    }
    if (abs(right_speed) > 0 && abs(right_speed) < 10)
    {
      if (right_speed > 0)
      {
        right_speed = 10;
      }
      if (right_speed < 0)
      {
        right_speed = -10;
      }
    }
  }

  left_speed = constrain(left_speed, -60, 60);
  right_speed = constrain(right_speed, -60, 60);
  int right_pwm = 0;
  int left_pwm = 0;

  if (IS_MOTORS_REVERSED == 1)
  {
    right_pwm = map(right_speed, -60, 60, 250, 125);
    left_pwm = map(left_speed, -60, 60, 125, 250);
  }
  else
  {
    right_pwm = map(right_speed, -60, 60, 125, 250);
    left_pwm = map(left_speed, -60, 60, 250, 125);
  }

  analogWrite(MotorLpwm, left_pwm);
  analogWrite(MotorRpwm, right_pwm);
}
void stop()
{
  analogWrite(MotorLpwm, 0);
  analogWrite(MotorRpwm, 0);
  // act_stop();
}
void act_up()
{
  // Serial.println("Moving Up");
  if (ToolType == 4)
  {
    analogWrite(act_rpwm, 254);
    analogWrite(act_lpwm, 0);
  }
  else
  {
    analogWrite(act_rpwm, 250);
    analogWrite(act_lpwm, 0);
  }
  // debug("act up  ");

  // analogWrite(Winch_PWM1, 250); // winch up down
  // analogWrite(Winch_PWM2, 0);

  // digitalWrite(Winch_PWM1, HIGH); // with arduino
}

void act_down()
{
  // Serial.println("Moving Down");
  if (ToolType == 4)
  {
    analogWrite(act_lpwm, 254);
    analogWrite(act_rpwm, 0);
  }
  else
  {
    analogWrite(act_lpwm, 250);
    analogWrite(act_rpwm, 0);
  }
  // debug("act down");

  // analogWrite(Winch_PWM1, 0); // winch up down
  // analogWrite(Winch_PWM2, 250);
  // digitalWrite(Winch_PWM2, HIGH); // with arduino
}
void act_stop()
{
  analogWrite(act_lpwm, 0);
  analogWrite(act_rpwm, 0);
  // analogWrite(Winch_PWM1, 0);
  // analogWrite(Winch_PWM2, 0);
  // debug("act stop");
}

void read_actuator()
{
  actuator = readChannel(ACT_CH, -100, 100, 0);

  ActuatorFB = (analogRead(ActuatorFB_PIN) / 10) * 10;
  Pot_Filter.Filter(ActuatorFB);
  ActuatorFB = Pot_Filter.Current();
  ActuatorFB = map(ActuatorFB, mini_range, max_range, 0, 100);

  if (actuator > 20 && (ToolType == 1 || ToolType == 2 || ToolType == 3 || ToolType == 4) && tools_halt == 0)
  {
    act_down();
  }

  else if (actuator < -20 && (ToolType == 1 || ToolType == 2 || ToolType == 3 || ToolType == 4) && tools_halt == 0)
  {
    act_up();
  }
  else
  {
    // read_imu();
    // depth_control();
    act_stop();
  }
}

void read_spd()
{
  // debug("enable on");
  // debug(" ");
  speed = readChannel(SPD_CH, -100, 100, 0);
  if (speed > 0)
  {
    // digitalWrite(LIGHT_RELAY, LOW);
    lane_follow = 0;
    max_spd = 60;
  }
  else if (speed < 0)
  {
    // digitalWrite(LIGHT_RELAY, HIGH);
    lane_follow = 1;
    // max_spd = 20;
  }
  else
  {
    lane_follow = 0;
    max_spd = 30;
  }
  // debug(" speed: ");
  // debug(speed);
}

void check_RK()
{
  if (lane_follow == 0)
  {
    rk_on = readChannel(RK_CH, -100, 100, 0);
    if (rk_on > 50)
    {
      Serial.println(100);
      if (Serial.available())
      {
        int direction_value = Serial.parseInt();
        if (direction_value == -100)
        {
          targetThrottle = 0;
          steer = 0;
          stop();
        }
        else
        {
          direction_value = constrain(direction_value, -20, 20);
          targetThrottle = 23 * spd_ratio;
          steer = direction_value;
          steer = constrain(steer, -15, 15);
        }
      }
    }
  }
}

class Driver_CAN
{
private:
  int requestIndex = 0;
  unsigned long lastRequestTime = 0;
  const unsigned long requestInterval = 50; // 1 second interval

public:
  void init()
  {
    int retryCount = 30; // Number of times to retry initializing the CAN bus

    while (retryCount > 0)
    {
      if (Can.read(CAN_RX_msg))
      {
        if (CAN_RX_msg.id == 0x701)
        {
          // Serial.println("Heartbeat received");
          CAN_sensor_status[0] = 1;
          break; // Exit the loop if heartbeat received
        }
      }
      else
      {
        debugln("Heartbeat not received");
        retryCount--;
        CAN_sensor_status[0] = 0;
        debug("Retrying... ");
        debugln(retryCount);
      }
      delay(100); // Add a delay between retries to avoid flooding the bus
    }
  }

  void read_driver_CAN()
  {
    unsigned long currentMillis = millis();
    if (currentMillis - lastRequestTime >= requestInterval)
    {
      lastRequestTime = currentMillis;
      switch (requestIndex)
      {
      case 0:
        sendSDORequest(0x210D, 0x02);
        break;
      case 1:
        sendSDORequest(0x210A, 0x01);
        break;
      case 2:
        sendSDORequest(0x210A, 0x02);
        break;
      case 3:
        sendSDORequest(0x210F, 0x01);
        break;
      case 4:
        sendSDORequest(0x2111, 0x00);
        break;
      case 5:
        sendSDORequest(0x2112, 0x00);
        break;
      case 6:
        sendSDORequest(0x2112, 0x01);
        break;
      case 7:
        sendSDORequest(0x2112, 0x02);
        break;
      }
      requestIndex = (requestIndex + 1) % 8; // Cycle through 8 requests
    }

    if (Can.read(CAN_RX_msg))
    {
      updateVariablesFromCAN(CAN_RX_msg);
      // printCANMessage(CAN_RX_msg);  // Optional: Print the CAN message for Serial.printging
      // printVariables(); // Optional: Print the updated variables
    }
  }

  void sendSDORequest(uint16_t index, uint8_t subindex)
  {
    CAN_message_t sdo_msg;
    sdo_msg.id = 0x601; // Assuming 0x601 is the node ID for SDO client
    sdo_msg.len = 8;
    sdo_msg.buf[0] = 0x40;         // SDO read command specifier
    sdo_msg.buf[1] = index & 0xFF; // LSB of index
    sdo_msg.buf[2] = index >> 8;   // MSB of index
    sdo_msg.buf[3] = subindex;     // Subindex
    for (int i = 4; i < 8; i++)
    {
      sdo_msg.buf[i] = 0x00; // Unused bytes
    }

    Can.write(sdo_msg);
  }

  void updateVariablesFromCAN(CAN_message_t &msg)
  {
    // if (msg.id != 0x701)
    { // Exclude the unwanted message ID
      uint16_t responseIndex = (uint16_t)((msg.buf[2] << 8) | msg.buf[1]);
      uint8_t responseSubIndex = msg.buf[3];
      switch (responseIndex)
      {
      case 0x210D:
        if (responseSubIndex == 0x01)
        {
          internalVoltagesVInt = (uint16_t)((msg.buf[5] << 8) | msg.buf[4]) / 10;
        }
        else if (responseSubIndex == 0x02)
        {
          DriverSupplyVoltage = ((msg.buf[5] << 8) | msg.buf[4]) / 10;
        }
        else if (responseSubIndex == 0x03)
        {
          internalVoltagesMV = (uint16_t)((msg.buf[5] << 8) | msg.buf[4]) / 1000;
        }
        break;
      case 0x210A:
        if (responseSubIndex == 0x01)
        {
          // Handle 0x210A sub-index 1
        }
        else if (responseSubIndex == 0x02)
        {
          // Handle 0x210A sub-index 2
        }
        break;
      case 0x210F:
        if (responseSubIndex == 0x01)
        {
          caseInternalTempMCU = (int8_t)msg.buf[4];
        }
        break;
      case 0x2111:
        if (responseIndex == 0x2111 && responseSubIndex == 0x00)
        {
          statusFlags = (uint8_t)msg.buf[4]; // Assuming status flags are in buf[4]
          // decodeStatusFlags();               // Call the function to decode status flags
        }
        break;
      case 0x2112:
        if (responseSubIndex == 0x00)
        {
          faultFlags = (uint8_t)msg.buf[4];
          // decodeFaultFlags();
        }
        if (responseSubIndex == 0x01 || responseSubIndex == 0x02)
        {
          // Serial.println("Read runtime flags: ");
          RuntimeStatusFlags = (uint8_t)msg.buf[4];
          // decodeRuntimeStatusFlags(responseSubIndex);
        }
        break;
        // Add any other cases you need
      }
    }
  }

  void decodeRuntimeStatusFlags(int ch)
  {
    debug("Decoding Runtime Status Flags: ");
    debug(ch);
    debug(" Amps Limit currently active: ");
    debug(RuntimeStatusFlags & 0x01 ? "Yes" : "No");

    debug(" | Motor stalled: ");
    debug(RuntimeStatusFlags & 0x02 ? "Yes" : "No");

    debug(" | Loop Error detected: ");
    debug(RuntimeStatusFlags & 0x04 ? "Yes" : "No");

    debug(" | Safety Stop active: ");
    debug(RuntimeStatusFlags & 0x08 ? "Yes" : "No");

    // debug(" Forward Limit triggered: ");
    // debug(RuntimeStatusFlags & 0x10 ? "Yes" : "No");

    // debug(" Reverse Limit triggered: ");
    // debug(RuntimeStatusFlags & 0x20 ? "Yes" : "No");

    debug(" | Amps Trigger activated: ");
    debugln(RuntimeStatusFlags & 0x40 ? "Yes" : "No");
  }

  void decodeFaultFlags()
  {
    debug("Decoding Fault Flags: ");
    debug("| Overheat: ");
    debugln(faultFlags & 0x01 ? "ON" : "OFF");
  }

  void decodeStatusFlags()
  {
    debug("Decoding Status Flags:");
    // debug("Serial mode: ");
    // debug(statusFlags & 0x01 ? "ON" : "OFF");
    debug(" | Pulse mode: ");
    debug(statusFlags & 0x02 ? "ON" : "OFF");
    // debug("Analog mode: ");
    // debug(statusFlags & 0x04 ? "ON" : "OFF");
    // debug("Power stage off: ");
    // debug(statusFlags & 0x08 ? "ON" : "OFF");
    debug(" | Stall detected: ");
    debug(statusFlags & 0x10 ? "ON" : "OFF");
    debug(" | At limit: ");
    debugln(statusFlags & 0x20 ? "ON" : "OFF");
    // f7 is unused
    // debug("MicroBasic script running: ");
    // debug(statusFlags & 0x80 ? "ON" : "OFF");
  }

  void printVariables()
  {
    debug(" blMotorSpeedInRPMCh1: ");
    debug(blMotorSpeedInRPMCh1);
    debug(" blMotorSpeedInRPMCh2: ");
    debug(blMotorSpeedInRPMCh2);
    debug(" DriverSupplyVoltage: ");
    debug(DriverSupplyVoltage);
    debug(" caseInternalTempMCU: ");
    debug(caseInternalTempMCU);
    debug(" statusFlags: ");
    debug(statusFlags);
    debug(" faultFlags: ");
    debug(faultFlags);
    debugln();
  }

  void printCANMessage(CAN_message_t &msg)
  {
    // Check for the specific ID and skip printing if it matches 0x701
    if (msg.id != 0x701)
    {
      debug("Channel:");
      debug(msg.bus);
      debug(msg.flags.extended ? " Extended ID:" : " Standard ID:");
#if DEBUG == 1
      Serial.print(msg.id, HEX);
#endif

      debug(" DLC: ");
      debug(msg.len);
      if (!msg.flags.remote)
      {
        debug(" buf: ");
        for (int i = 0; i < msg.len; i++)
        {
          debug("0x");
#if DEBUG == 1
          Serial.print(msg.buf[i], HEX);
#endif
          if (i != (msg.len - 1))
            debug(" ");
        }
        debugln();
      }
      else
      {
        debugln(" Data: REMOTE REQUEST FRAME");
      }
    }
  }
};

Driver_CAN driver_can_data;

class Telemetry_Tx
{
public:
  void rec_data()
  {
    if (telemetry_serial.available())
    {
      receiveData();
    }

    if (newTelemetryData)
    {
      // Serial.println(mainReceivedString);
      decodeData(mainReceivedString);
      // print_recd_data();
      newTelemetryData = false;
    }
  }
  void receiveData()
  {
    static String tempString; // Changed to static to preserve data between function calls
    while (telemetry_serial.available() > 0)
    {
      char receivedChar = telemetry_serial.read();

      tempString += receivedChar;
      tempString.trim();

      if (receivedChar == '<' && (tempString.length() > 1))
      {
        tempString = "";
      }

      if (receivedChar == '>')
      {
        tempString.trim(); // Remove leading and trailing whitespace including newline chars
        // debugln("Received Line: " + tempString);  // Debugging: Print the line

        // Check if the string is valid
        if (tempString.startsWith("<") && tempString.endsWith(">")) // && tempString.length() < 75) // actual max length is 68
        {
          mainReceivedString = tempString.substring(1, tempString.length() - 1);
          newTelemetryData = true;
        }
        tempString = ""; // Clear the temporary string after processing
      }
    }
  }
  void Rotavator_control()
  {
    if (ToolType == 3 && tool_on_off_button && tools_halt == 0) // Rotavator
    {
      if (HAS_PTO_DAC == 1)
      {
        // debug("Rotavator ON ");
        float Rotavator_speed = 0;
        switch (tooldata[5]) // speed
        {
        case 1:
          Rotavator_speed = 2.14; //  Low 2.14V
          break;
        case 2:
          Rotavator_speed = 2.72; // Medium 2.72V
          break;
        case 3:
          Rotavator_speed = 3.26; // High 3.26V
          break;
        default:
          Rotavator_speed = 0.0;
          break;
        }

        if (current_rotavator_speed == 0)
        {
          PTO_DAC.setVoltage(Rotavator_speed);
          current_rotavator_speed = 1;
        }
      }
      else
      {
        // debug("Rotavator ON ");
        int Rotavator_speed = 0;
        switch (tooldata[5]) // speed
        {
        case 1:
          Rotavator_speed = 107; //  Low 2.14V
          break;
        case 2:
          Rotavator_speed = 135; // Medium 2.72V
          break;
        case 3:
          Rotavator_speed = 160; // High 3.26V
          break;
        default:
          Rotavator_speed = 50;
          break;
        }
        analogWrite(PTO_PWM_PIN, Rotavator_speed);
      }
    }
    else
    {
      if (HAS_PTO_DAC == 1)
      {
        if (current_rotavator_speed != 0)
        {
          // Rotavator_speed = 0.9;
          PTO_DAC.setVoltage(0.9);
          current_rotavator_speed = 0;
        }
      }
      else
      {
        analogWrite(PTO_PWM_PIN, 50);
      }
    }
  }

  void decodeData(String str)
  {
    int index = 0;
    int lastIndex = 0;

    // Decode timestamp and message ID
    index = str.indexOf(',', lastIndex);
    telem_Timestamp = str.substring(lastIndex, index);
    lastIndex = index + 1;
    index = str.indexOf(',', lastIndex);
    messageID = str.substring(lastIndex, index).toInt();
    lastIndex = index + 1;

    if (messageID == 0)
    {
      // Decode ControlMode to telem_dummy2
      for (int i = 0; i < 7; ++i)
      {
        index = str.indexOf(',', lastIndex);
        if (index == -1)
          index = str.length();
        int value = str.substring(lastIndex, index).toInt();
        switch (i)
        {
        case 0:
          ControlMode = value;
          break;
        case 1:
          PathMode = value;
          break;
        case 2:
          Lights = value;
          break;
        case 3:
          App_Emergency = value;
          break;
        case 4:
          ToolType = value;
          break;
        case 5:
          Tool_On_Off = value;
          break; // Added Tool_On_Off
        case 6:
          telem_dummy2 = value;
          break; // Added telem_dummy2
        }
        lastIndex = index + 1;
      }
    }
    else if (messageID == 4)
    {
      basic_data_req = 1;
    }
    else
    {
      // Serial.println(str);
      // Decode tooldata
      for (int i = 0; i < 17; ++i)
      { // Adjusted to 7 for the tooldata array
        index = str.indexOf(',', lastIndex);
        if (index == -1)
          index = str.length();
        tooldata[i] = str.substring(lastIndex, index).toInt();
        lastIndex = index + 1;
      }
    }
  }

  void sendData(String dataString)
  {
    // String dataString = "<"; // Start indicator
    // for (int i = 0; i < txDataSize; i++)
    // {
    //   dataString += String(dataToSend[i]);
    //   if (i < txDataSize - 1)
    //     dataString += ","; // Add delimiter
    // }
    // dataString += ">"; // End indicator

    // Convert the string to a byte array and send it
    const char *byteData = dataString.c_str();
    telemetry_serial.write(byteData, strlen(byteData));
    telemetry_serial.println();
  }

  long get_timestamp()
  {
    return 0;
  }

  int getBatteryPercentage()
  {
    if (RSOC > 20)
    {
      return RSOC;
    }
    return 1; // Return 1% if voltage is below the lowest threshold
  }

  int get_T1MortorTemp()
  {
    return temp1;
  }

  int get_T2MortorTemp()
  {
    return temp2;
  }

  int get_T3MortorDriverTemp()
  {
    return temp3;
  }

  int get_WaterLevelValue()
  {
    return 30;
  }

  int get_Steering_angle()
  {
    return map(steer, -60, 60, -200, 200);
  }

  int temp_delta_check()
  {
    if (abs(abs(temp1) - abs(temp2)) > 20) // delta between two motor temp > 20
    {
      if (abs(temp1) > abs(temp2))
      {
        // intimate temp1 is very high than temp2..  contact FR support
        return 1;
      }
      else
      {
        // intimate temp2 is very high than temp1..  contact FR support
        return 2;
      }
    }
    else
    {
      // no temp delta
      return 0;
    }
  }

  void check_tools_halt()
  {
    // halt tools for conditons ultra-low battery, temp too high, temp delta high
    if (dataToSend[2] <= 10 || dataToSend[3] >= 90 || dataToSend[4] >= 90 || dataToSend[5] >= 90 || dataToSend[13] != 0)
    {
      tools_halt = 1;
    }
    else
    {
      tools_halt = 0;
    }
  }

  void EmergencyAlert()
  {
    dataToSend[8] = 0;
    dataToSend[9] = 0;
    dataToSend[10] = 0;
    dataToSend[11] = 0;
    dataToSend[12] = 0;

    if (dataToSend[2] <= 30)
    {
      // Serial.println("Battery is Low!");
      dataToSend[8] = 1;
    }
    else if (dataToSend[2] <= 10)
    {
      // Serial.println("Battery is too Low, plan for charging  halting all the tools!");
      // dataToSend[8] = 2;
    }

    if (dataToSend[3] >= 70 && dataToSend[3] < 90)
    {
      // Serial.println("T1 temp is high, give rest to bot!");
      dataToSend[9] = 1;
    }
    else if (dataToSend[3] >= 90)
    {
      // Serial.println("T1 temp is too high, stopping the tools in the bot for cooldown!");
      // dataToSend[9] = 2;
    }

    if (dataToSend[4] >= 70 && dataToSend[4] < 90)
    {
      // Serial.println("T2 temp is high, give rest to bot!");
      dataToSend[10] = 1;
    }
    else if (dataToSend[4] >= 90)
    {
      // Serial.println("T2 temp is too high, stopping the tools in the bot for cooldown!");
      // dataToSend[10] = 2;
    }

    if (dataToSend[5] >= 70 && dataToSend[5] < 90)
    {
      // Serial.println("T3 temp is high!");
      dataToSend[11] = 1;
    }
    else if (dataToSend[5] >= 90)
    {
      // Serial.println("T3 temp is too high, stopping the tools in the bot for cooldown!");
      // dataToSend[11] = 2;
    }

    if (dataToSend[6] <= 15)
    {
      // Serial.println("Low Water Level");
      dataToSend[12] = 1;
    }
    dataToSend[13] = 0;             // temp_delta_check(); // Bot Emergency switch alert
    dataToSend[14] = !bumper_alarm; // Bumper sensor alert
    dataToSend[15] = 0;             // Internal error (contact service)
  }
  void process()
  {
    if (basic_data_req == 1)
    {
      int msg_ID = 2;

      String dataString = "<";

      dataString += String(msg_ID) + ",";
      dataString += String(2) + ","; // Robot name dummy data
      dataString += String(ROBOT_ID) + ",";
      dataString += String(robot_version) + ",";
      dataString += String(software_version) + ",";
      dataString += String(is_blade) + ",";
      dataString += String(is_tyne) + ",";
      dataString += String(is_rotovator) + ",";
      dataString += String(is_boomsprayer) + ",";
      dataString += String(is_mistblower) + ",";
      dataString += String(is_trailer) + ",";
      dataString += String(0) + ",";
      dataString += String(0) + ",";
      dataString += String(0) + ",";
      dataString += String(0) + ",";
      dataString += String(0) + ",";
      dataString += ">";
      sendData(dataString);
      basic_data_req = 0;
    }

    delay(1);
    int msg_ID = 3;

    dataToSend[0] = 3; // msg ID
    dataToSend[1] = get_timestamp();
    dataToSend[2] = getBatteryPercentage();
    dataToSend[3] = get_T1MortorTemp();
    dataToSend[4] = get_T2MortorTemp();
    dataToSend[5] = get_T3MortorDriverTemp();
    dataToSend[6] = get_WaterLevelValue();
    dataToSend[7] = get_Steering_angle();
    EmergencyAlert();
    // check_tools_halt();
    tools_halt = 0;

    String dataString = "<"; // Start indicator
    for (int i = 0; i < txDataSize; i++)
    {
      dataString += String(dataToSend[i]);
      if (i < txDataSize - 1)
        dataString += ","; // Add delimiter
    }
    dataString += ">"; // End indicator

    sendData(dataString);
    delay(1);
    rec_data();
    Rotavator_control();
  }
};

Telemetry_Tx bot2app_telem;

class BATTERY_BMS_CAN
{
public:
  void init()
  {
    int retryCount = 30; // Number of times to retry initializing the CAN bus

    while (retryCount > 0)
    {
      sendRequest(0x100);
      debugln("Request sent successfully");
      if (Can.read(CAN_RX_msg))
      {
        if (CAN_RX_msg.id == 0x100)
        {
          debugln("CAN OK");
          CAN_sensor_status[1] = 1;
          break; // Set flag to true to exit the loop
        }
      }
      else
      {
        debugln("No CAN msg recd");
        retryCount--;
        CAN_sensor_status[1] = 0;
        debug("Retrying... ");
        debugln(retryCount);
      }
      delay(100);
    }
  }
  void update()
  {
    sendRequests();
    readCANMessages();
    // print_can_params();
  }

  void sendRequest(uint16_t index)
  {
    CAN_message_t CAN_TX_msg;
    CAN_TX_msg.id = index;
    CAN_TX_msg.len = 1;
    CAN_TX_msg.buf[0] = 0x5A;
    Can.write(CAN_TX_msg);
  }

  void print_can_params()
  {
    // debug("Received Message ID: ");
    // debug(CAN_RX_msg.id, HEX);
    // for (int i = 0; i < CAN_RX_msg.len; i++) {
    //   debug(" 0x");
    //   if (CAN_RX_msg.buf[i] < 0x10)
    //     debug("0");
    //   debug(CAN_RX_msg.buf[i], HEX);
    //   debug(" ");
    // }
    // debugln();

    debug(" BMSVoltage ");
    debug(BMSVoltage);
    debug(" BMScurrent ");
    debug(BMScurrent);
    debug(" remainingCapacity ");
    debug(remainingCapacity);
    debug(" fullCapacity ");
    debug(fullCapacity);
    debug(" cycleTimes ");
    debug(cycleTimes);
    debug(" RSOC ");
    debug(RSOC);
    debug(" balanceStatus ");
    debug(balanceStatus);
    debug(" protectionStatus ");
    debug(protectionStatus);
    debug(" FETControlStatus ");
    debug(FETControlStatus);
    // debug(" productionDate ");
    // debug(productionDate);
    // debug(" seriesOfBattery ");
    // debug(seriesOfBattery);
    // debug(" NTCNumbers ");
    // debug(NTCNumbers);
    debug(" NTC1Temp ");
    debug(NTC1Temp);
    debug(" NTC2Temp ");
    debug(NTC2Temp);
    debug(" NTC3Temp ");
    debug(NTC3Temp);
    debug(" NTC4Temp ");
    debug(NTC4Temp);
    debug(" NTC5Temp ");
    debug(NTC5Temp);
    // debug(" NTC6Temp ");
    // debug(NTC6Temp);
    debug(" cellVoltages ");
    for (int i = 0; i <= 15; i++)
    {
      debug(cellVoltages[i]);
      debug(" ");
    }
    debugln();
  }

  void sendRequests()
  {
    unsigned long currentMillis = millis();

    // Send a request every second
    if (currentMillis - BMSlastSent >= 50)
    {
      BMSlastSent = currentMillis;

      // Send request for current ID
      if (BMScurrentIDIndex < sizeof(critical_data_IDs) / sizeof(critical_data_IDs[0]))
      {
        sendRequest(critical_data_IDs[BMScurrentIDIndex]);
      }
      else
      {
        sendRequest(normal_data_IDs[BMScurrentIDIndex - sizeof(critical_data_IDs) / sizeof(critical_data_IDs[0])]);
      }

      // Move to next ID
      BMScurrentIDIndex++;
      if (BMScurrentIDIndex >= (sizeof(critical_data_IDs) / sizeof(critical_data_IDs[0])) + (sizeof(normal_data_IDs) / sizeof(normal_data_IDs[0])))
      {
        BMScurrentIDIndex = 0; // Reset index after last ID
      }
    }
  }

  void readCANMessages()
  {
    // Read incoming messages
    if (Can.read(CAN_RX_msg))
    {
      switch (CAN_RX_msg.id)
      {
      case 0x100:
        BMSVoltage = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]) / 100.0; // Assuming 100 is the conversion factor
        BMScurrent = (int16_t)(CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        if (BMScurrent != 0)
        {
          BMScurrent = abs(BMScurrent) / 100.0;
        }
        remainingCapacity = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x101:
        fullCapacity = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        cycleTimes = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        RSOC = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x102:
        balanceStatus = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        // Assign the highbyte of balance status
        balanceStatus |= (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        protectionStatus = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x103:
        FETControlStatus = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        // productionDate = String(CAN_RX_msg.buf[2]) + "/" + String(CAN_RX_msg.buf[3]);
        // softwareVersion = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      // case 0x104:
      //   seriesOfBattery = CAN_RX_msg.buf[0];
      //   NTCNumbers = CAN_RX_msg.buf[1];
      //   break;
      case 0x105:
        NTC1Temp = ((CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]) - 2731) / 10;
        NTC2Temp = ((CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]) - 2731) / 10;
        NTC3Temp = ((CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]) - 2731) / 10;
        break;
      case 0x106:
        NTC4Temp = ((CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]) - 2731) / 10;
        NTC5Temp = ((CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]) - 2731) / 10;
        // NTC6Temp = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x107:
        cellVoltages[0] = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        cellVoltages[1] = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        cellVoltages[2] = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x108:
        cellVoltages[3] = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        cellVoltages[4] = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        cellVoltages[5] = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x109:
        cellVoltages[6] = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        cellVoltages[7] = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        cellVoltages[8] = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x10A:
        cellVoltages[9] = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        cellVoltages[10] = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        cellVoltages[11] = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x10B:
        cellVoltages[12] = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        cellVoltages[13] = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        cellVoltages[14] = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      case 0x10C:
        cellVoltages[15] = (CAN_RX_msg.buf[0] << 8 | CAN_RX_msg.buf[1]);
        // cellVoltages[16] = (CAN_RX_msg.buf[2] << 8 | CAN_RX_msg.buf[3]);
        // cellVoltages[17] = (CAN_RX_msg.buf[4] << 8 | CAN_RX_msg.buf[5]);
        break;
      }
    }
  }
};

BATTERY_BMS_CAN can_bms_data;

class datalogging_Tx
{
public:
  void SendCriticalData()
  {
    DL_message_ID = 4;

    String dataString = "<"; // Start indicator
    // Add all variables to the data string
    dataString += String(DL_message_ID) + ",";
    dataString += String(temp1) + ",";
    dataString += String(temp2) + ",";
    dataString += String(temp3) + ",";
    dataString += String(BMScurrent) + ",";
    dataString += String(currentThrottle) + ",";
    dataString += String(steer) + ",";
    dataString += String(bumper_alarm) + ",";
    dataString += String(ActuatorFB) + ",";
    dataString += ErrorMessage + ",";
    dataString += String(looptime) + ",";
    dataString += String(messageID) + ",";
    dataString += String(ControlMode) + ",";
    dataString += String(PathMode) + ",";
    dataString += String(Lights) + ",";
    dataString += String(App_Emergency) + ",";
    dataString += String(ToolType) + ",";
    dataString += String(Tool_On_Off) + ",";
    dataString += String(telem_dummy2) + ",";
    dataString += String(tooldata[0]) + ",";
    dataString += String(tooldata[1]) + ",";
    dataString += String(tooldata[2]) + ",";
    dataString += String(tooldata[3]) + ",";
    dataString += String(tooldata[4]) + ",";
    dataString += String(tooldata[5]) + ",";
    dataString += String(tooldata[6]) + ",";
    dataString += String(blMotorSpeedInRPMCh1) + ",";
    dataString += String(blMotorSpeedInRPMCh2) + ",";
    dataString += String(DriverSupplyVoltage) + ",";
    dataString += String(caseInternalTempMCU) + ",";
    dataString += String(caseInternalTempCh1) + ",";
    dataString += String(caseInternalTempCh2) + ",";
    dataString += String(0) + ","; // Current2Filter.Current()
    dataString += String(faultFlags) + ",";
    dataString += String(BMSVoltage) + ",";
    dataString += String(BMScurrent) + ",";
    dataString += String(RSOC) + ",";
    dataString += String(NTC1Temp) + ",";
    dataString += String(NTC2Temp) + ",";
    dataString += String(NTC3Temp) + ",";
    dataString += String(NTC4Temp) + ",";
    dataString += String(NTC5Temp);
    // dataString += String(NTC6Temp);

    dataString += ">"; // End indicator

    // Convert the string to a byte array and send it
    const char *byteData = dataString.c_str();
    // datalogging_serial.write(byteData, strlen(byteData));
    // datalogging_serial.println();
    telemetry_serial.write(byteData, strlen(byteData));
    telemetry_serial.println();
  }

  void SendNormalData()
  {
    DL_message_ID = 5;

    String dataString = "<"; // Start indicator
    // Add variables to the data string
    dataString += String(DL_message_ID) + ",";
    dataString += String(remainingCapacity) + ",";
    dataString += String(fullCapacity) + ",";
    dataString += String(cycleTimes) + ",";
    dataString += String(balanceStatus) + ",";
    dataString += String(protectionStatus) + ",";
    dataString += String(FETControlStatus) + ",";
    // dataString += productionDate + ",";
    // dataString += String(softwareVersion) + ",";
    // dataString += String(seriesOfBattery) + ",";
    // dataString += String(NTCNumbers) + ",";
    for (int i = 0; i < 16; i++)
    {
      dataString += String(cellVoltages[i]);
      if (i < 16)
        dataString += ",";
    }
    // for (int i = 16; i < 30; i++)
    // {
    //   dataString += String(i + 1); // cellVoltages[i]);
    //   if (i < 29)
    //     dataString += ",";
    // }

    dataString += ">"; // End indicator

    // Convert the string to a byte array and send it
    const char *byteData = dataString.c_str();
    // datalogging_serial.write(byteData, strlen(byteData));
    // datalogging_serial.println();
    telemetry_serial.write(byteData, strlen(byteData));
    telemetry_serial.println();
  }
  void sendToApp()
  {
    // Send data based on the time elapsed
    unsigned long currentMillis = millis();

    if (currentMillis - lastCriticalDataTime >= 1000)
    {
      lastCriticalDataTime = currentMillis;
      SendCriticalData();
    }
    else if (currentMillis - lastNormalDataTime >= 5000)
    {
      lastNormalDataTime = currentMillis;
      SendNormalData();
    }
  }
};

datalogging_Tx data2telem;

void check_sensor_status()
{
  if (CAN_sensor_status[0] == 0 && CAN_sensor_status[1] == 0)
  {
    debugln("Neither CAN bus is OK. Not proceeding...");
  }
  else if (CAN_sensor_status[0] == 1 && CAN_sensor_status[1] == 1)
  {
    debugln("Both CAN buses are OK. Proceeding...");
  }
  else
  {
    if (CAN_sensor_status[0] == 1)
    {
      debugln("only Driver CAN bus is OK. Proceeding...");
    }
    else
    {
      debugln("only BMS CAN bus is OK. Proceeding...");
    }
  }
}

void setup()
{
  Serial.begin(115200);
  // SPI.setMISO(PB4);
  // SPI.setMOSI(PB5);
  // SPI.setSCLK(PB3);

  pinMode(MotorLpwm, OUTPUT);
  pinMode(MotorRpwm, OUTPUT);
  pinMode(LIGHT_RELAY, OUTPUT);
  pinMode(PANEL_FAN_RELAY, OUTPUT);
  pinMode(BOTTOM_FAN_RELAY, OUTPUT);
  pinMode(HORN_RELAY, OUTPUT);
  pinMode(act_lpwm, OUTPUT);
  pinMode(act_rpwm, OUTPUT);
  // pinMode(Winch_PWM1, OUTPUT);
  // pinMode(Winch_PWM2, OUTPUT);

  Wire.setSDA(SDA_PIN);
  Wire.setSCL(SCL_PIN);
  Wire.begin();
  Wire.setTimeout(100);
  if (HAS_PTO_DAC == 1)
  {
    PTO_DAC.setMaxVoltage(5.1);
    PTO_DAC.setVoltage(0.9);
    current_rotavator_speed = 0;
  }
  else
  {
    analogWrite(PTO_PWM_PIN, 50);
  }
  // digitalWrite(LIGHT_RELAY, HIGH);
  // digitalWrite(PANEL_FAN_RELAY, HIGH);
  // digitalWrite(BOTTOM_FAN_RELAY, HIGH);
  digitalWrite(HORN_RELAY, HIGH);

  analogWriteFrequency(490);
  analogWriteResolution(8);
  analogReadResolution(10);

  BUMPER_SENSOR.setDebounceTime(50);

  telemetry_serial.begin(115200);
  delay(100);

  tool_serial.begin(115200);
  delay(100);

  sbus_rx.Begin();

  stop();
  act_stop();

  temp1_sensor.begin();
  temp2_sensor.begin();
  // temp3_sensor.begin();
  temp1_sensor.setWaitForConversion(false);
  temp2_sensor.setWaitForConversion(false);
  // temp3_sensor.setWaitForConversion(false);

  Can.begin();
  Can.setBaudRate(500000); // 500KBPS

  // driver_can_data.init();
  // can_bms_data.init();

  // check_sensor_status();

  delay(20);
}

void loop()
{
  BUMPER_SENSOR.loop();
  bumper_alarm = BUMPER_SENSOR.getState();

  if (sbus_rx.Read())
  {
    sbus_data = sbus_rx.data();

    if (sbus_data.failsafe == 0 && sbus_data.lost_frame == 0 && App_Emergency == 0)
    {
      last_sbus_data = millis();
      ErrorMessage = "run";
      read_actuator();

      enable_switch = readChannel(ENA_CH, -100, 100, 0);
      // debug(" enable");
      // debug(enable_switch);
      tool_on_off_button = readChannel(TOOL_CH, 0, 1, 0);

      if (enable_switch > 50 && App_Emergency == 0)
      {

        read_spd();
        calc_throttle_steer();
        updateMotorSpeeds(currentThrottle, steer);
      }
      else
      {
        ErrorMessage = "Enable switch off";
        stop();
      }
      if (abs(readChannel(HORN_CH, -100, 100, 0)) > 20)
      {
        digitalWrite(HORN_RELAY, LOW);
      }
      else
      {
        digitalWrite(HORN_RELAY, HIGH);
      }
    }
    else
    {
      ErrorMessage = "sbus_failsafe_issue";
      stop();
    }
  }

  if (millis() - last_sbus_data >= 1500)
  {
    ErrorMessage = "SBus delay stop";
    stop();
  }

  if (Lights == 1)
  {
    if (lights_count < 0)
    {
      lights_count = 0;
    }
    if (lights_count >= 5)
    {
      digitalWrite(LIGHT_RELAY, LOW);
      lights_count = 0;
    }
    else
    {
      lights_count = lights_count + 1;
    }
  }
  else
  {
    if (lights_count > 0)
    {
      lights_count = 0;
    }
    if (lights_count <= -5)
    {
      digitalWrite(LIGHT_RELAY, HIGH);
      lights_count = 0;
    }
    else
    {
      lights_count = lights_count - 1;
    }
  }
  current1 = BMScurrent;
  driver_can_data.read_driver_CAN();
  bot2app_telem.process();
  can_bms_data.update();

  data2telem.sendToApp();
  if (millis() - lastLoggedTime >= 1000)
  {
    // It's been long enough since the last request, so we can read the temperature now
    float temp_t1 = temp1_sensor.getTempCByIndex(0);
    float temp_t2 = temp2_sensor.getTempCByIndex(0);
    if (temp_t1 > 0)
    {
      temp1 = temp_t1;
      temp1_count = 0;
    }
    else
    {
      temp1_count += 1;
    }
    if (temp_t2 > 0)
    {
      temp2 = temp_t2;
      temp2_count = 0;
    }
    else
    {
      temp2_count += 1;
    }
    if (temp1_count > 40)
    {
      temp1 = 0;
      temp1_count = 0;
    }
    if (temp2_count > 40)
    {
      temp2 = 0;
      temp2_count = 0;
    }
    // Start a new temperature conversion
    temp1_sensor.requestTemperatures();
    temp2_sensor.requestTemperatures();
    temp3 = caseInternalTempMCU;

    if (temp1 > 50 || temp2 > 50)
    {
      digitalWrite(BOTTOM_FAN_RELAY, LOW);
      // debugln("BOTTOM FAN ON");
    }
    else
    {
      // debugln("BOTTOM FAN OFF");
      digitalWrite(BOTTOM_FAN_RELAY, HIGH);
    }

    if (caseInternalTempMCU > 45)
    {
      digitalWrite(PANEL_FAN_RELAY, LOW);
      // debugln("PANEL FAN ON");
    }
    else
    {
      // debugln("PANEL FAN OFF");
      digitalWrite(PANEL_FAN_RELAY, HIGH);
    }

    // sd_write();
    lastLoggedTime = millis();
  }
  looptime = millis() - prev_looptime;
  prev_looptime = millis();
  debugging();
  debugln();
  can_bms_data.print_can_params();
}
