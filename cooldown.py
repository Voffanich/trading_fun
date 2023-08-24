import datetime
from datetime import datetime as dt


class Cooldown():
    
    def __init__(self, deal_config: dict, db: object):
        self.CHECK_PERIOD = datetime.timedelta(hours=deal_config['cool_down_check_period'])
        self.LOSS_QUANTITY = deal_config['cool_down_loss_quantity']
        self.LENGTH = datetime.timedelta(hours=deal_config['cool_down_length'])
        
        self.start_time = dt.now()
        self.finish_time = dt.now()
        
        self.lost_deals_timestamps: list = db.last_lost_deals_times(self.LOSS_QUANTITY)
        
        
    def add_lost_deal(self, bot: object, chat_id: int):
        if len(self.lost_deals_timestamps) < self.LOSS_QUANTITY:
            self.lost_deals_timestamps.append(dt.now())
        else:
            self.lost_deals_timestamps.append(dt.now())
            self.lost_deals_timestamps.pop(0)
            
            if self.lost_deals_timestamps[-1] - self.lost_deals_timestamps[0] <= self.CHECK_PERIOD:
                self.start_time = dt.now()
                self.finish_time = dt.now() + self.LENGTH
                
                print(f'-- Cooldown set from {dt.strftime(self.start_time, "%Y-%m-%d %H:%M:%S")} to {dt.strftime(self.finish_time, "%Y-%m-%d %H:%M:%S")}')
                
                message = f"""
                <b>Cooldown set from {dt.strftime(self.start_time, "%Y-%m-%d %H:%M:%S")} to {dt.strftime(self.finish_time, "%Y-%m-%d %H:%M:%S")}</b>
                """
            
                bot.send_message(chat_id, text = message, parse_mode = 'HTML')
                
        
    def status_on(self) -> bool:
        if dt.now() <= self.finish_time:
            return True
        else:
            return False
        
        
    def get_start_time(self) -> object:
        return self.start_time
    
    
    def get_finish_time(self) -> object:
        return self.finish_time
    
    
    def get_lost_deals_timestamps(self) -> list:
        return self.lost_deals_timestamps