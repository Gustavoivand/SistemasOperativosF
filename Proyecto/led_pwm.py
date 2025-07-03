from machine import Pin, PWM

class LED:
    def __init__(self, pin_num, freq=1500):
        self.pin_num = pin_num
        self.freq = freq
        self.pwm = PWM(Pin(pin_num), freq=freq)
        self.is_on = False  # Track the LED state
        self.min_percent = 0
        self.percent = 0  # Track the brightness state
        self.duty = int(self.min_percent / 100 * 1023)  # Track the duty state
        
    def on(self, percentage = 0):
        if percentage > 0:
            self.percent = percentage
            self.duty = int(percentage / 100 * 1023)
            
        self.pwm.duty(self.duty)  # Set duty cycle to 1023 (maximum value) to fully turn on the LED
        self.is_on = True  # Update LED state
        
    def off(self):
        self.pwm.duty(0)  # Set duty cycle to 0 to fully turn off the LED
        self.is_on = False  # Update LED state
        
    def set_brightness(self, percentage):
        if percentage > 0:
            # Convert percentage to a duty cycle value between 0 and 1023 (100%)
            pvalue = percentage if percentage > self.min_percent else self.min_percent
            self.percent = percentage
            self.duty = int(pvalue / 100 * 1023)
            if self.is_on == True:
                self.pwm.duty(self.duty)  # Set duty cycle to the calculated value

        else:
            self.off()
        

    def get_brightness(self):
        # when off, return brightness value as 0
        if self.is_on == False:
            return 0

        return self.percent

    def set_value(self, state):
        if state == 0:
            self.off()
        elif state == 1:
            self.on()
        else:
            raise ValueError("Invalid state value. Use 0 for off and 1 for on.")
            
    def value(self):
        return 1 if self.is_on == True else 0  # Return current LED state (1 if on, 0 if off)
                
    def deinit(self):
        self.pwm.deinit()  # Deinitialize the PWM to clean up