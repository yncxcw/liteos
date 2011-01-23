#include "sounder.h"
#include "leds.h"
#include "thread.h"
#include "adc.h"
#include "radio.h"
#include "serial.h"
#include "file.h"
#include "system.h"



int main()
{

 uint8_t index;  
 __asm__ __volatile__("sei" ::); 
 
   for (index = 0;index <5;index++)
   	{
	   
	   greenToggle(); 
	   sounderOn();     
	   sleepThread(2000);
	   sounderOff();
     sleepThread(2000);
    }
   
	return 0; 
}

