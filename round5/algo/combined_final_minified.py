_BK='UV_VISOR_RED'
_BJ='PANEL_2X4'
_BI='UV_VISOR_ORANGE'
_BH='TRANSLATOR_VOID_BLUE'
_BG='PANEL_2X2'
_BF='TRANSLATOR_GRAPHITE_MIST'
_BE='PANEL_1X2'
_BD='PANEL_4X4'
_BC='stop_mult'
_BB='exit_frac'
_BA='grid_spread_mult'
_B9='grid_vol_mult'
_B8='extended_wait_mult'
_B7='MICROCHIP_SQUARE'
_B6='last_timestamp'
_B5='GALAXY_SOUNDS_SOLAR_WINDS'
_B4='SLEEP_POD_COTTON'
_B3='SLEEP_POD_LAMB_WOOL'
_B2='SNACKPACK_VANILLA'
_B1='PEBBLES_L'
_B0='UV_VISOR_AMBER'
_A_='cool_ticks'
_Az='paired_strong_direction'
_Ay='pair_gap_frac'
_Ax='pair_move_frac'
_Aw='OXYGEN_SHAKE_GARLIC'
_Av='OXYGEN_SHAKE_EVENING_BREATH'
_Au='OXYGEN_SHAKE_CHOCOLATE'
_At='detect_direction'
_As='MICROCHIP_RECTANGLE'
_Ar='ROBOT_IRONING'
_Aq='ROBOT_DISHES'
_Ap='GALAXY_SOUNDS_SOLAR_FLAMES'
_Ao='GALAXY_SOUNDS_DARK_MATTER'
_An='GALAXY_SOUNDS_PLANETARY_RINGS'
_Am='SLEEP_POD_SUEDE'
_Al='SNACKPACK_RASPBERRY'
_Ak='SNACKPACK_STRAWBERRY'
_Aj='SNACKPACK_PISTACHIO'
_Ai='SNACKPACK_CHOCOLATE'
_Ah='PEBBLES_XS'
_Ag='__substates'
_Af='max_spread'
_Ae='MICROCHIP_OVAL'
_Ad='WAIT'
_Ac='rel_last'
_Ab='prev'
_Aa='open'
_AZ='target'
_AY='xl_buffer_dir'
_AX='xl_raw_signal'
_AW='PEBBLES_XL'
_AV='PEBBLES_M'
_AU='PEBBLES_S'
_AT='gate50'
_AS='gate20'
_AR='ref_alpha'
_AQ='trend_active_dir'
_AP='entry_rel'
_AO='pair_size'
_AN='rel_vol'
_AM='rel_anchor'
_AL='rel_slow'
_AK='GALAXY_SOUNDS_BLACK_HOLES'
_AJ='vol'
_AI='anchor'
_AH='slow'
_AG='fast'
_AF='obs'
_AE='pebble_sum_ref'
_AD='xl_confirmed_signal'
_AC='cover_anchor'
_AB='pair_count'
_AA='pair_var'
_A9='pair_mean'
_A8='neutral_cooldown'
_A7='spread_floor'
_A6='spread_gate_mult'
_A5='wait_entry_ref'
_A4='wait_entry_dir'
_A3='active_dir'
_A2='rel_fast'
_A1='pair'
_A0='short_count'
_z='long_count'
_y='xl_signal_count'
_x='abs_ewma'
_w='min_conf_ratio'
_v='confirm_ticks'
_u='det_pct'
_t='det_spread_mult'
_s='det_vol_mult'
_r='min_count'
_q='layer_dir'
_p='short_anchor'
_o='neutral_entry_dir'
_n='bad_count'
_m='good_count'
_l='rel_history'
_k='layer_ref'
_j=':'
_i=','
_h='ema_gap_frac'
_g='reentry_frac'
_f='cover_pct'
_e='cover_spread_mult'
_d='cover_vol_mult'
_c='layer_entry'
_b=True
_a='raw_dir'
_Z='count'
_Y='paused_dir'
_X='xl_paused_dir'
_W='neutral_ref'
_V='ema_slow'
_U='ema_fast'
_T='neutral_entry'
_S='confirmed_dir'
_R='xl_exit_anchor'
_Q='vol_ema'
_P='raw_dir_count'
_O='spread_ema'
_N='SHORT'
_M='LONG'
_L=.0
_K='xl_entry_anchor'
_J='grid_dir'
_I='grid_entry'
_H='grid_ref'
_G='mode'
_F='exit_anchor'
_E='last_mid'
_D='init_mid'
_C='entry_anchor'
_B=1.
_A=None
from datamodel import OrderDepth,UserId,TradingState,Order
from typing import List,Dict,Optional,Tuple,Any
import json,math
class _PebblesStrategy:
	POSITION_LIMIT=10;XS=_Ah;S=_AU;M=_AV;L=_B1;XL=_AW;TRADED={XS,S,M,L,XL};ALL_PEBBLES=[XS,S,M,L,XL];SHORT_COVER_BUFFER={XS:2e2,S:2e2};SHORT_REENTRY_BUFFER={XS:1e2,S:1e2};M_GRID_THRESHOLD=3e2;L_GRID_THRESHOLD=1e2;XL_COVER_BUFFER=1e2;XL_REENTRY_BUFFER=1e2;XL_LONG_XSS_TRIGGER=45e1;XL_LONG_REST_MIN=25e1;XL_LONG_REST_STRONG=9e2;XL_LONG_ML_MAX=1e2;XL_SHORT_ML_TRIGGER=8e2;XL_SHORT_REST_MIN=3e2;XL_SHORT_REST_STRONG=1e3;XL_SHORT_ML_MIN=7e2;XL_CONFIRM_COUNT=2
	def bid(self):return 15
	def best_bid_ask(self,order_depth):best_bid=max(order_depth.buy_orders.keys())if order_depth.buy_orders else _A;best_ask=min(order_depth.sell_orders.keys())if order_depth.sell_orders else _A;return best_bid,best_ask
	def mid_price(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is not _A and best_ask is not _A:return(best_bid+best_ask)/2.
		if best_bid is not _A:return float(best_bid)
		if best_ask is not _A:return float(best_ask)
	def spread(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is _A or best_ask is _A:return
		return best_ask-best_bid
	def fresh_data(self):return{_D:{},_E:{},_p:{},_AC:{},_H:{},_I:{},_J:{},_AX:0,_y:0,_AD:0,_AY:0,_K:_A,_R:_A,_X:0,_AE:_A}
	def load_data(self,trader_data,timestamp):
		if timestamp==0:return self.fresh_data()
		if not trader_data:return self.fresh_data()
		try:data=json.loads(trader_data)
		except Exception:return self.fresh_data()
		data.setdefault(_D,{});data.setdefault(_E,{});data.setdefault(_p,{});data.setdefault(_AC,{});data.setdefault(_H,{});data.setdefault(_I,{});data.setdefault(_J,{});data.setdefault(_AX,0);data.setdefault(_y,0);data.setdefault(_AD,0);data.setdefault(_AY,0);data.setdefault(_K,_A);data.setdefault(_R,_A);data.setdefault(_X,0);data.setdefault(_AE,_A);return data
	def update_state(self,data,mids):
		for product in self.ALL_PEBBLES:
			if product not in mids:continue
			mid=mids[product]
			if product not in data[_D]:data[_D][product]=mid
			data[_E][product]=mid
	def buffered_short_target(self,product,order_depth,current_position,data):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is _A and best_ask is _A:return current_position
		cover_buffer=self.SHORT_COVER_BUFFER[product];reentry_buffer=self.SHORT_REENTRY_BUFFER[product];short_anchor=data[_p].get(product);cover_anchor=data[_AC].get(product)
		if current_position<0:
			if short_anchor is _A:
				if best_bid is not _A:short_anchor=float(best_bid)
				else:mid=self.mid_price(order_depth);short_anchor=float(mid)if mid is not _A else _L
				data[_p][product]=short_anchor
			if best_bid is not _A and best_bid>=short_anchor+cover_buffer:
				if best_ask is not _A:data[_AC][product]=float(best_ask)
				else:data[_AC][product]=float(best_bid)
				return 0
			return-self.POSITION_LIMIT
		else:
			if current_position>0:return 0
			if cover_anchor is _A:
				if best_bid is not _A:data[_p][product]=float(best_bid)
				else:mid=self.mid_price(order_depth);data[_p][product]=float(mid)if mid is not _A else _L
				return-self.POSITION_LIMIT
			if best_bid is not _A and best_bid>=cover_anchor+reentry_buffer:data[_p][product]=float(best_bid);return-self.POSITION_LIMIT
			return 0
	def reset_grid_position_state(self,data,product):data[_I][product]=_A;data[_J][product]=0
	def long_only_grid_target(self,product,order_depth,current_position,data,threshold):
		best_bid,best_ask=self.best_bid_ask(order_depth);mid=self.mid_price(order_depth)
		if best_bid is _A and best_ask is _A and mid is _A:return current_position
		if product not in data[_H]or data[_H].get(product)is _A:data[_H][product]=float(mid if mid is not _A else best_ask if best_ask is not _A else best_bid);self.reset_grid_position_state(data,product)
		ref=float(data[_H][product]);entry=data[_I].get(product)
		if current_position<0:self.reset_grid_position_state(data,product);return 0
		if current_position>0:
			if entry is _A:entry=float(mid if mid is not _A else best_ask if best_ask is not _A else best_bid);data[_I][product]=entry;data[_J][product]=1
			if best_bid is not _A and best_bid>=entry+threshold:data[_H][product]=float(best_bid);self.reset_grid_position_state(data,product);return 0
			return self.POSITION_LIMIT
		self.reset_grid_position_state(data,product)
		if best_ask is not _A and best_ask<=ref-threshold:data[_I][product]=float(best_ask);data[_J][product]=1;return self.POSITION_LIMIT
		return 0
	def symmetric_grid_target(self,product,order_depth,current_position,data,threshold):
		best_bid,best_ask=self.best_bid_ask(order_depth);mid=self.mid_price(order_depth)
		if best_bid is _A and best_ask is _A and mid is _A:return current_position
		if product not in data[_H]or data[_H].get(product)is _A:data[_H][product]=float(mid if mid is not _A else best_ask if best_ask is not _A else best_bid);self.reset_grid_position_state(data,product)
		ref=float(data[_H][product]);entry=data[_I].get(product)
		if current_position>0:
			if entry is _A:entry=float(mid if mid is not _A else best_ask if best_ask is not _A else best_bid);data[_I][product]=entry;data[_J][product]=1
			if best_bid is not _A and best_bid>=entry+threshold:data[_H][product]=float(best_bid);self.reset_grid_position_state(data,product);return 0
			return self.POSITION_LIMIT
		if current_position<0:
			if entry is _A:entry=float(mid if mid is not _A else best_bid if best_bid is not _A else best_ask);data[_I][product]=entry;data[_J][product]=-1
			if best_ask is not _A and best_ask<=entry-threshold:data[_H][product]=float(best_ask);self.reset_grid_position_state(data,product);return 0
			return-self.POSITION_LIMIT
		self.reset_grid_position_state(data,product)
		if best_ask is not _A and best_ask<=ref-threshold:data[_I][product]=float(best_ask);data[_J][product]=1;return self.POSITION_LIMIT
		if best_bid is not _A and best_bid>=ref+threshold:data[_I][product]=float(best_bid);data[_J][product]=-1;return-self.POSITION_LIMIT
		return 0
	def pebble_identity_ok(self,data,mids):
		if not all(p in mids for p in self.ALL_PEBBLES):return False
		pebble_sum=sum(mids[p]for p in self.ALL_PEBBLES)
		if data.get(_AE)is _A:data[_AE]=pebble_sum;return _b
		return abs(pebble_sum-data[_AE])<=250
	def compute_xl_signal(self,data,mids):
		required=[self.XS,self.S,self.M,self.L,self.XL]
		if not all(p in mids for p in required):return 0
		init=data[_D]
		if not all(p in init for p in required):return 0
		xs_s_now=mids[self.XS]+mids[self.S];xs_s_init=init[self.XS]+init[self.S];xs_s_move=xs_s_now-xs_s_init;ml_now=mids[self.M]+mids[self.L];ml_init=init[self.M]+init[self.L];ml_move=ml_now-ml_init;rest4_move=xs_s_move+ml_move;short_signal=ml_move>self.XL_SHORT_ML_TRIGGER and rest4_move>self.XL_SHORT_REST_MIN or rest4_move>self.XL_SHORT_REST_STRONG and ml_move>self.XL_SHORT_ML_MIN;long_signal=xs_s_move<-self.XL_LONG_XSS_TRIGGER and ml_move<self.XL_LONG_ML_MAX and rest4_move<-self.XL_LONG_REST_MIN or rest4_move<-self.XL_LONG_REST_STRONG and ml_move<self.XL_LONG_ML_MAX
		if short_signal:return-1
		if long_signal:return 1
		return 0
	def confirmed_xl_signal(self,data,raw_signal):
		if raw_signal==0:return data.get(_AD,0)
		prev_raw=data.get(_AX,0)
		if raw_signal==prev_raw:data[_y]=data.get(_y,0)+1
		else:data[_y]=1;data[_AX]=raw_signal
		if data[_y]>=self.XL_CONFIRM_COUNT:data[_AD]=raw_signal
		return data.get(_AD,0)
	def reset_xl_buffer(self,data,direction):data[_AY]=direction;data[_K]=_A;data[_R]=_A;data[_X]=0
	def buffered_xl_target(self,order_depth,current_position,desired_signal,desired_abs_position,data):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is _A and best_ask is _A:return current_position
		if desired_signal==0 or desired_abs_position<=0:self.reset_xl_buffer(data,0);return 0
		desired_abs_position=max(0,min(self.POSITION_LIMIT,desired_abs_position))
		if data.get(_AY,0)!=desired_signal:self.reset_xl_buffer(data,desired_signal)
		entry_anchor=data.get(_K);exit_anchor=data.get(_R);paused_dir=data.get(_X,0);mid=self.mid_price(order_depth)
		if desired_signal>0:
			if current_position>0:
				if entry_anchor is _A:
					if best_ask is not _A:entry_anchor=float(best_ask)
					elif mid is not _A:entry_anchor=float(mid)
					else:entry_anchor=_L
					data[_K]=entry_anchor
				if best_ask is not _A and best_ask<=entry_anchor-self.XL_COVER_BUFFER:
					if best_bid is not _A:data[_R]=float(best_bid)
					else:data[_R]=float(best_ask)
					data[_K]=_A;data[_X]=1;return 0
				return desired_abs_position
			else:
				if paused_dir!=1 or exit_anchor is _A:
					if best_ask is not _A:data[_K]=float(best_ask)
					elif mid is not _A:data[_K]=float(mid)
					else:data[_K]=_L
					data[_R]=_A;data[_X]=0;return desired_abs_position
				if best_ask is not _A and best_ask<=exit_anchor-self.XL_REENTRY_BUFFER:data[_K]=float(best_ask);data[_R]=_A;data[_X]=0;return desired_abs_position
				return 0
		elif current_position<0:
			if entry_anchor is _A:
				if best_bid is not _A:entry_anchor=float(best_bid)
				elif mid is not _A:entry_anchor=float(mid)
				else:entry_anchor=_L
				data[_K]=entry_anchor
			if best_bid is not _A and best_bid>=entry_anchor+self.XL_COVER_BUFFER:
				if best_ask is not _A:data[_R]=float(best_ask)
				else:data[_R]=float(best_bid)
				data[_K]=_A;data[_X]=-1;return 0
			return-desired_abs_position
		else:
			if paused_dir!=-1 or exit_anchor is _A:
				if best_bid is not _A:data[_K]=float(best_bid)
				elif mid is not _A:data[_K]=float(mid)
				else:data[_K]=_L
				data[_R]=_A;data[_X]=0;return-desired_abs_position
			if best_bid is not _A and best_bid>=exit_anchor+self.XL_REENTRY_BUFFER:data[_K]=float(best_bid);data[_R]=_A;data[_X]=0;return-desired_abs_position
			return 0
	def orders_to_target(self,product,order_depth,current_position,target_position,max_spread):
		orders=[];target_position=max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target_position));delta=target_position-current_position
		if delta==0:return orders
		sp=self.spread(order_depth);reducing_risk=abs(target_position)<abs(current_position)
		if sp is not _A and sp>max_spread and not reducing_risk:return orders
		if delta>0:
			need=delta
			for(ask,ask_volume)in sorted(order_depth.sell_orders.items()):
				if need<=0:break
				available=-ask_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,ask,qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=min(best_bid+1,best_ask-1)
					if price>best_bid:orders.append(Order(product,price,need))
				elif best_bid is not _A:orders.append(Order(product,best_bid+1,need))
		elif delta<0:
			need=-delta
			for(bid,bid_volume)in sorted(order_depth.buy_orders.items(),reverse=_b):
				if need<=0:break
				available=bid_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,bid,-qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=max(best_ask-1,best_bid+1)
					if price<best_ask:orders.append(Order(product,price,-need))
				elif best_ask is not _A:orders.append(Order(product,best_ask-1,-need))
		return orders
	def run_with_data(self,state,trader_data):
		result={};data=self.load_data(trader_data,state.timestamp);mids={}
		for(product,order_depth)in state.order_depths.items():
			mid=self.mid_price(order_depth)
			if mid is not _A:mids[product]=mid
		self.update_state(data,mids);identity_ok=self.pebble_identity_ok(data,mids)
		for product in state.order_depths:result[product]=[]
		for product in[self.XS,self.S]:
			if product not in state.order_depths:continue
			current_position=state.position.get(product,0);target=self.buffered_short_target(product=product,order_depth=state.order_depths[product],current_position=current_position,data=data);result[product]=self.orders_to_target(product=product,order_depth=state.order_depths[product],current_position=current_position,target_position=target,max_spread=80)
		if self.M in state.order_depths:current_position=state.position.get(self.M,0);target=self.long_only_grid_target(product=self.M,order_depth=state.order_depths[self.M],current_position=current_position,data=data,threshold=self.M_GRID_THRESHOLD);result[self.M]=self.orders_to_target(product=self.M,order_depth=state.order_depths[self.M],current_position=current_position,target_position=target,max_spread=100)
		if self.L in state.order_depths:current_position=state.position.get(self.L,0);target=self.symmetric_grid_target(product=self.L,order_depth=state.order_depths[self.L],current_position=current_position,data=data,threshold=self.L_GRID_THRESHOLD);result[self.L]=self.orders_to_target(product=self.L,order_depth=state.order_depths[self.L],current_position=current_position,target_position=target,max_spread=100)
		if self.XL in state.order_depths and identity_ok:
			raw_xl_signal=self.compute_xl_signal(data,mids);xl_signal=self.confirmed_xl_signal(data,raw_xl_signal)
			if raw_xl_signal!=0 and xl_signal!=0 and raw_xl_signal!=xl_signal:desired_signal=0;desired_abs_position=0
			elif xl_signal!=0:desired_signal=xl_signal;desired_abs_position=10
			elif raw_xl_signal!=0:desired_signal=raw_xl_signal;desired_abs_position=5
			else:desired_signal=0;desired_abs_position=0
			current_position=state.position.get(self.XL,0);xl_target=self.buffered_xl_target(order_depth=state.order_depths[self.XL],current_position=current_position,desired_signal=desired_signal,desired_abs_position=desired_abs_position,data=data);result[self.XL]=self.orders_to_target(product=self.XL,order_depth=state.order_depths[self.XL],current_position=current_position,target_position=xl_target,max_spread=100)
		elif self.XL in state.order_depths:self.reset_xl_buffer(data,0);current_position=state.position.get(self.XL,0);result[self.XL]=self.orders_to_target(product=self.XL,order_depth=state.order_depths[self.XL],current_position=current_position,target_position=0,max_spread=100)
		traderData=json.dumps(data,separators=(_i,_j));conversions=0;return result,conversions,traderData
class _SnackpackStrategy:
	POSITION_LIMIT=10;CHOCOLATE=_Ai;VANILLA=_B2;PISTACHIO=_Aj;STRAWBERRY=_Ak;RASPBERRY=_Al;TRADED={CHOCOLATE,VANILLA,PISTACHIO,STRAWBERRY,RASPBERRY};SYMMETRIC_GRID_LAYERS={CHOCOLATE:[(125.,2),(15e1,8)],VANILLA:[(125.,2),(15e1,8)],RASPBERRY:[(75.,8),(1e2,2)],PISTACHIO:[(75.,5),(15e1,5)],STRAWBERRY:[(3e2,4),(4e2,6)]}
	def bid(self):return 15
	def best_bid_ask(self,order_depth):best_bid=max(order_depth.buy_orders.keys())if order_depth.buy_orders else _A;best_ask=min(order_depth.sell_orders.keys())if order_depth.sell_orders else _A;return best_bid,best_ask
	def mid_price(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is not _A and best_ask is not _A:return(best_bid+best_ask)/2.
		if best_bid is not _A:return float(best_bid)
		if best_ask is not _A:return float(best_ask)
	def spread(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is _A or best_ask is _A:return
		return best_ask-best_bid
	def usable_price(self,order_depth):
		mid=self.mid_price(order_depth)
		if mid is not _A:return mid
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is not _A:return float(best_bid)
		if best_ask is not _A:return float(best_ask)
	def fresh_data(self):return{_k:{},_c:{},_q:{},_E:{}}
	def load_data(self,trader_data,timestamp):
		if timestamp==0:return self.fresh_data()
		if not trader_data:return self.fresh_data()
		try:data=json.loads(trader_data)
		except Exception:return self.fresh_data()
		data.setdefault(_k,{});data.setdefault(_c,{});data.setdefault(_q,{});data.setdefault(_E,{});return data
	def layer_key(self,product,layer_idx):return product+'#'+str(layer_idx)
	def init_layer_if_needed(self,data,key,initial_price):
		if key not in data[_k]or data[_k].get(key)is _A:data[_k][key]=float(initial_price);data[_c][key]=_A;data[_q][key]=0
	def reset_layer_position_state(self,data,key):data[_c][key]=_A;data[_q][key]=0
	def update_last_mid(self,data,product,mid):
		if mid is not _A:data[_E][product]=mid
	def layered_symmetric_grid_target(self,product,order_depth,data):
		best_bid,best_ask=self.best_bid_ask(order_depth);usable=self.usable_price(order_depth)
		if usable is _A:return 0
		target=0;layers=self.SYMMETRIC_GRID_LAYERS[product]
		for(idx,(threshold,qty))in enumerate(layers):
			key=self.layer_key(product,idx);self.init_layer_if_needed(data,key,usable);ref=float(data[_k][key]);entry=data[_c].get(key);layer_dir=int(data[_q].get(key,0))
			if layer_dir>0:
				if entry is _A:entry=usable;data[_c][key]=float(entry)
				if best_bid is not _A and best_bid>=float(entry)+threshold:data[_k][key]=float(best_bid);self.reset_layer_position_state(data,key);layer_dir=0
				else:target+=qty;continue
			elif layer_dir<0:
				if entry is _A:entry=usable;data[_c][key]=float(entry)
				if best_ask is not _A and best_ask<=float(entry)-threshold:data[_k][key]=float(best_ask);self.reset_layer_position_state(data,key);layer_dir=0
				else:target-=qty;continue
			if layer_dir==0:
				if best_ask is not _A and best_ask<=ref-threshold:data[_c][key]=float(best_ask);data[_q][key]=1;target+=qty
				elif best_bid is not _A and best_bid>=ref+threshold:data[_c][key]=float(best_bid);data[_q][key]=-1;target-=qty
		return max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target))
	def orders_to_target(self,product,order_depth,current_position,target_position,max_spread):
		orders=[];target_position=max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target_position));delta=target_position-current_position
		if delta==0:return orders
		sp=self.spread(order_depth);reducing_risk=abs(target_position)<abs(current_position)
		if sp is not _A and sp>max_spread and not reducing_risk:return orders
		if delta>0:
			need=delta
			for(ask,ask_volume)in sorted(order_depth.sell_orders.items()):
				if need<=0:break
				available=-ask_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,ask,qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=min(best_bid+1,best_ask-1)
					if price>best_bid:orders.append(Order(product,price,need))
				elif best_bid is not _A:orders.append(Order(product,best_bid+1,need))
		elif delta<0:
			need=-delta
			for(bid,bid_volume)in sorted(order_depth.buy_orders.items(),reverse=_b):
				if need<=0:break
				available=bid_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,bid,-qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=max(best_ask-1,best_bid+1)
					if price<best_ask:orders.append(Order(product,price,-need))
				elif best_ask is not _A:orders.append(Order(product,best_ask-1,-need))
		return orders
	def run_with_data(self,state,trader_data):
		result={};data=self.load_data(trader_data,state.timestamp)
		for product in state.order_depths:result[product]=[]
		for product in self.TRADED:
			if product not in state.order_depths:continue
			order_depth=state.order_depths[product];current_position=state.position.get(product,0);mid=self.mid_price(order_depth);self.update_last_mid(data,product,mid);target_position=self.layered_symmetric_grid_target(product=product,order_depth=order_depth,data=data);result[product]=self.orders_to_target(product=product,order_depth=order_depth,current_position=current_position,target_position=target_position,max_spread=80)
		traderData=json.dumps(data,separators=(_i,_j));conversions=0;return result,conversions,traderData
class _SleepPodStrategy:
	LIMIT=10;SUEDE=_Am;LAMB=_B3;POLY='SLEEP_POD_POLYESTER';NYLON='SLEEP_POD_NYLON';COTTON=_B4;PRODUCTS=[SUEDE,LAMB,POLY,NYLON,COTTON];BASE_PRODUCT=SUEDE;FAST_ALPHA=2./17.;SLOW_ALPHA=2./101.;ANCHOR_ALPHA=2./251.;VOL_ALPHA=2./61.;MIN_OBS_FOR_ADAPTIVE=450;OPEN_MOVE_SPREAD_MULT=5.;OPEN_MOVE_VOL_MULT=6.;CONFIRM_COUNT=3;ADAPTIVE_SIZE=10
	def run_with_data(self,state,trader_data):
		A='pods';result={};data=self._load_state(trader_data)
		if A not in data:data[A]={}
		for product in self.PRODUCTS:
			if product not in data[A]:data[A][product]=self._new_memory()
		mids,spreads=self._read_market(state)
		for product in self.PRODUCTS:
			if product in mids:self._update_memory(memory=data[A][product],mid=mids[product],spread=spreads[product])
		targets={p:0 for p in self.PRODUCTS}
		if self.SUEDE in mids:targets[self.SUEDE]=self.LIMIT
		for product in[self.LAMB,self.POLY,self.NYLON,self.COTTON]:
			if product not in mids:continue
			target=self._adaptive_target(memory=data[A][product],mid=mids[product],spread=spreads[product]);targets[product]=target
		for product in self.PRODUCTS:
			if product not in state.order_depths:continue
			position=state.position.get(product,0);target=max(-self.LIMIT,min(self.LIMIT,int(targets.get(product,0))));orders=self._move_to_target(product=product,order_depth=state.order_depths[product],position=position,target=target)
			if orders:result[product]=orders
		return result,0,self._dump_state(data)
	def _adaptive_target(self,memory,mid,spread):
		if memory[_AF]<self.MIN_OBS_FOR_ADAPTIVE:return memory.get(_AZ,0)
		open_mid=memory[_Aa];fast=memory[_AG];slow=memory[_AH];anchor=memory[_AI];vol=max(_B,memory[_AJ]);open_move=mid-open_mid;fast_slow=fast-slow;anchor_move=mid-anchor;required_move=max(self.OPEN_MOVE_SPREAD_MULT*spread,self.OPEN_MOVE_VOL_MULT*vol);long_signal=open_move>required_move and fast_slow>0 and anchor_move>-.25*required_move;short_signal=open_move<-required_move and fast_slow<0 and anchor_move<.25*required_move
		if long_signal:memory[_z]+=1;memory[_A0]=0
		elif short_signal:memory[_A0]+=1;memory[_z]=0
		else:memory[_z]=max(0,memory[_z]-1);memory[_A0]=max(0,memory[_A0]-1)
		target=memory.get(_AZ,0)
		if memory[_z]>=self.CONFIRM_COUNT:target=self.ADAPTIVE_SIZE
		elif memory[_A0]>=self.CONFIRM_COUNT:target=-self.ADAPTIVE_SIZE
		memory[_AZ]=target;return target
	def _update_memory(self,memory,mid,spread):
		memory[_AF]+=1
		if memory[_Aa]is _A:memory[_Aa]=mid;memory[_Ab]=mid;memory[_AG]=mid;memory[_AH]=mid;memory[_AI]=mid;memory[_AJ]=max(_B,.35*spread);return
		prev=memory[_Ab];diff=mid-prev;memory[_Ab]=mid;memory[_AG]=self.FAST_ALPHA*mid+(_B-self.FAST_ALPHA)*memory[_AG];memory[_AH]=self.SLOW_ALPHA*mid+(_B-self.SLOW_ALPHA)*memory[_AH];memory[_AI]=self.ANCHOR_ALPHA*mid+(_B-self.ANCHOR_ALPHA)*memory[_AI];memory[_AJ]=self.VOL_ALPHA*abs(diff)+(_B-self.VOL_ALPHA)*memory[_AJ]
	def _read_market(self,state):
		mids={};spreads={}
		for product in self.PRODUCTS:
			od=state.order_depths.get(product)
			if od is _A or not od.buy_orders or not od.sell_orders:continue
			best_bid=max(od.buy_orders.keys());best_ask=min(od.sell_orders.keys());mids[product]=(best_bid+best_ask)/2.;spreads[product]=max(_B,best_ask-best_bid)
		return mids,spreads
	def _move_to_target(self,product,order_depth,position,target):
		orders=[]
		if position==target:return orders
		if not order_depth.buy_orders or not order_depth.sell_orders:return orders
		delta=target-position
		if delta>0:self._buy(product,order_depth,orders,delta)
		elif delta<0:self._sell(product,order_depth,orders,-delta)
		return orders
	def _buy(self,product,order_depth,orders,quantity):
		remaining=quantity
		for ask in sorted(order_depth.sell_orders.keys()):
			if remaining<=0:break
			available=-order_depth.sell_orders[ask]
			if available<=0:continue
			take=min(remaining,available);orders.append(Order(product,ask,take));remaining-=take
	def _sell(self,product,order_depth,orders,quantity):
		remaining=quantity
		for bid in sorted(order_depth.buy_orders.keys(),reverse=_b):
			if remaining<=0:break
			available=order_depth.buy_orders[bid]
			if available<=0:continue
			take=min(remaining,available);orders.append(Order(product,bid,-take));remaining-=take
	def _new_memory(self):return{_AF:0,_Aa:_A,_Ab:_A,_AG:_A,_AH:_A,_AI:_A,_AJ:_B,_z:0,_A0:0,_AZ:0}
	def _load_state(self,trader_data):
		if not trader_data:return{}
		try:
			data=json.loads(trader_data)
			if isinstance(data,dict):return data
		except Exception:pass
		return{}
	def _dump_state(self,data):
		try:return json.dumps(data,separators=(_i,_j))
		except Exception:return'{}'
class _GalaxyStrategy:
	LIMIT=10;BLACK=_AK;RINGS=_An;GALAXY_PRODUCTS=[_Ao,_AK,_An,_B5,_Ap];FAST_ALPHA=2./19.;SLOW_ALPHA=2./121.;ANCHOR_ALPHA=2./601.;VOL_ALPHA=2./91.;PROBE_SIZE=3;SAFE_SIZE=5;FULL_SIZE=10
	def run_with_data(self,state,trader_data):
		result={};data=self._load_state(trader_data)
		if _A1 not in data:data[_A1]=self._new_pair_memory()
		mids={};spreads={}
		for product in self.GALAXY_PRODUCTS:
			od=state.order_depths.get(product)
			if od is _A or not od.buy_orders or not od.sell_orders:continue
			best_bid=max(od.buy_orders.keys());best_ask=min(od.sell_orders.keys());mids[product]=(best_bid+best_ask)/2.;spreads[product]=max(_B,best_ask-best_bid)
		targets={p:0 for p in self.GALAXY_PRODUCTS}
		if self.BLACK in mids and self.RINGS in mids:pair_size=self._adaptive_pair_size(memory=data[_A1],timestamp=state.timestamp,black_mid=mids[self.BLACK],rings_mid=mids[self.RINGS],black_spread=spreads[self.BLACK],rings_spread=spreads[self.RINGS]);targets[self.BLACK]=pair_size;targets[self.RINGS]=-pair_size
		for product in self.GALAXY_PRODUCTS:
			if product not in state.order_depths:continue
			position=state.position.get(product,0);target=max(-self.LIMIT,min(self.LIMIT,targets.get(product,0)));orders=self._move_to_target(product=product,order_depth=state.order_depths[product],position=position,target=target)
			if orders:result[product]=orders
		return result,0,self._dump_state(data)
	def _adaptive_pair_size(self,memory,timestamp,black_mid,rings_mid,black_spread,rings_spread):
		rel=black_mid-rings_mid;pair_cost=black_spread+rings_spread;memory[_AF]+=1;memory[_B6]=timestamp
		if memory[_A2]is _A:memory[_A2]=rel;memory[_AL]=rel;memory[_AM]=rel;memory[_Ac]=rel;memory[_AN]=_B;memory[_AO]=self.PROBE_SIZE;memory[_AP]=rel;return self.PROBE_SIZE
		prev_rel=memory[_Ac];d_rel=rel-prev_rel;memory[_Ac]=rel;memory[_A2]=self.FAST_ALPHA*rel+(_B-self.FAST_ALPHA)*memory[_A2];memory[_AL]=self.SLOW_ALPHA*rel+(_B-self.SLOW_ALPHA)*memory[_AL];memory[_AM]=self.ANCHOR_ALPHA*rel+(_B-self.ANCHOR_ALPHA)*memory[_AM];memory[_AN]=self.VOL_ALPHA*abs(d_rel)+(_B-self.VOL_ALPHA)*memory[_AN];noise=max(_B,memory[_AN],.3*pair_cost);rel_fast=memory[_A2];rel_slow=memory[_AL];rel_anchor=memory[_AM];health=0
		if rel_fast>rel_slow+.2*noise:health+=1
		elif rel_fast<rel_slow-.2*noise:health-=1
		if rel>rel_anchor+.25*noise:health+=1
		elif rel<rel_anchor-.25*noise:health-=1
		memory[_l].append(rel)
		if len(memory[_l])>80:memory[_l]=memory[_l][-80:]
		recent_momentum=_L
		if len(memory[_l])>=20:
			recent_momentum=memory[_l][-1]-memory[_l][-20]
			if recent_momentum>1.5*noise:health+=1
			elif recent_momentum<-1.5*noise:health-=1
		entry_rel=memory.get(_AP)
		if entry_rel is not _A:
			adverse=entry_rel-rel
			if adverse>max(4.*noise,1.5*pair_cost):health-=2
		if health>=2:memory[_m]+=1;memory[_n]=max(0,memory[_n]-1)
		elif health<=-2:memory[_n]+=1;memory[_m]=max(0,memory[_m]-1)
		else:memory[_m]=max(0,memory[_m]-1);memory[_n]=max(0,memory[_n]-1)
		current_size=int(memory.get(_AO,0))
		if memory[_n]>=8:new_size=0
		elif memory[_n]>=4:new_size=self.PROBE_SIZE
		elif memory[_m]>=5:new_size=self.FULL_SIZE
		elif memory[_m]>=2:new_size=max(current_size,self.SAFE_SIZE)
		elif current_size==0:
			if health>0:new_size=self.PROBE_SIZE
			else:new_size=0
		else:new_size=current_size
		if current_size==0 and health<=0:new_size=0
		if current_size==0 and new_size>0:memory[_AP]=rel
		if new_size==0:memory[_AP]=_A
		if abs(new_size-current_size)<2 and new_size!=0:new_size=current_size
		memory[_AO]=int(max(0,min(self.LIMIT,new_size)));return memory[_AO]
	def _move_to_target(self,product,order_depth,position,target):
		orders=[]
		if position==target:return orders
		if not order_depth.buy_orders or not order_depth.sell_orders:return orders
		delta=target-position
		if delta>0:self._take_asks(product,order_depth,orders,delta)
		elif delta<0:self._hit_bids(product,order_depth,orders,-delta)
		return orders
	def _take_asks(self,product,order_depth,orders,quantity):
		remaining=quantity
		for ask in sorted(order_depth.sell_orders.keys()):
			if remaining<=0:break
			available=-order_depth.sell_orders[ask]
			if available<=0:continue
			take=min(remaining,available);orders.append(Order(product,ask,take));remaining-=take
	def _hit_bids(self,product,order_depth,orders,quantity):
		remaining=quantity
		for bid in sorted(order_depth.buy_orders.keys(),reverse=_b):
			if remaining<=0:break
			available=order_depth.buy_orders[bid]
			if available<=0:continue
			take=min(remaining,available);orders.append(Order(product,bid,-take));remaining-=take
	def _new_pair_memory(self):return{_AF:0,_B6:_A,_A2:_A,_AL:_A,_AM:_A,_Ac:_A,_AN:_B,_l:[],_AP:_A,_m:0,_n:0,_AO:0}
	def _load_state(self,trader_data):
		if not trader_data:return{}
		try:
			data=json.loads(trader_data)
			if isinstance(data,dict):return data
		except Exception:pass
		return{}
	def _dump_state(self,data):
		try:return json.dumps(data,separators=(_i,_j))
		except Exception:return'{}'
class _RobotStrategy:
	POSITION_LIMIT=10;ROBOT_DISHES=_Aq;ROBOT_MOPPING='ROBOT_MOPPING';ROBOT_LAUNDRY='ROBOT_LAUNDRY';ROBOT_IRONING=_Ar;TRADED={ROBOT_DISHES,ROBOT_MOPPING,ROBOT_LAUNDRY,ROBOT_IRONING};DISHES_GRID_THRESHOLD=8e1;EARLY_DETECT_END=5000;EARLY_HIT_THRESHOLD=5e1;EARLY_FALLBACK_THRESHOLD=2e1;MOPPING_INVALIDATE_THRESHOLD=3e2;MOPPING_COVER_BUFFER=3e2;MOPPING_REENTRY_BUFFER=1e2;LAUNDRY_COVER_BUFFER=35e1;LAUNDRY_REENTRY_BUFFER=15e1;IRONING_CONFIRM_THRESHOLD=3e2;IRONING_COVER_BUFFER=2e2;IRONING_REENTRY_BUFFER=125.;MAX_SPREAD_TO_OPEN=25
	def bid(self):return 15
	def fresh_data(self):return{_D:{},_E:{},_G:{},_H:{},_I:{},_J:{},_AQ:{},_C:{},_F:{},_Y:{}}
	def load_data(self,trader_data,timestamp):
		if timestamp==0:return self.fresh_data()
		if not trader_data:return self.fresh_data()
		try:data=json.loads(trader_data)
		except Exception:return self.fresh_data()
		data.setdefault(_D,{});data.setdefault(_E,{});data.setdefault(_G,{});data.setdefault(_H,{});data.setdefault(_I,{});data.setdefault(_J,{});data.setdefault(_AQ,{});data.setdefault(_C,{});data.setdefault(_F,{});data.setdefault(_Y,{});return data
	def save_data(self,data):return json.dumps(data,separators=(_i,_j))
	def update_mid_state(self,data,product,mid):
		if product not in data[_D]:data[_D][product]=mid
		data[_E][product]=mid
	def best_bid_ask(self,od):best_bid=max(od.buy_orders.keys())if od.buy_orders else _A;best_ask=min(od.sell_orders.keys())if od.sell_orders else _A;return best_bid,best_ask
	def mid_price(self,od):
		best_bid,best_ask=self.best_bid_ask(od)
		if best_bid is not _A and best_ask is not _A:return(best_bid+best_ask)/2.
		if best_bid is not _A:return float(best_bid)
		if best_ask is not _A:return float(best_ask)
	def spread(self,od):
		best_bid,best_ask=self.best_bid_ask(od)
		if best_bid is _A or best_ask is _A:return
		return best_ask-best_bid
	def update_mopping_laundry_mode(self,data,product,mid,timestamp):
		mode=data[_G].get(product,_Ad);open_mid=float(data[_D][product]);move=mid-open_mid
		if mode in(_M,_N):
			if product==self.ROBOT_MOPPING:
				if mode==_N and move>=self.MOPPING_INVALIDATE_THRESHOLD:data[_G][product]=_M;self.reset_trend_state(data,product);return _M
				if mode==_M and move<=-self.MOPPING_INVALIDATE_THRESHOLD:data[_G][product]=_N;self.reset_trend_state(data,product);return _N
			return mode
		if mode=='OFF':return mode
		if timestamp<=self.EARLY_DETECT_END:
			if move>=self.EARLY_HIT_THRESHOLD:data[_G][product]=_M;self.reset_trend_state(data,product);return _M
			if move<=-self.EARLY_HIT_THRESHOLD:data[_G][product]=_N;self.reset_trend_state(data,product);return _N
			return _Ad
		if move>=self.EARLY_FALLBACK_THRESHOLD:data[_G][product]=_M;self.reset_trend_state(data,product);return _M
		if move<=-self.EARLY_FALLBACK_THRESHOLD:data[_G][product]=_N;self.reset_trend_state(data,product);return _N
		data[_G][product]='OFF';return'OFF'
	def update_ironing_mode(self,data,product,mid):
		mode=data[_G].get(product,_Ad)
		if mode in(_M,_N,'OFF'):return mode
		open_mid=float(data[_D][product]);move=mid-open_mid
		if move>=self.IRONING_CONFIRM_THRESHOLD:data[_G][product]=_M;self.reset_trend_state(data,product);return _M
		if move<=-self.IRONING_CONFIRM_THRESHOLD:data[_G][product]=_N;self.reset_trend_state(data,product);return _N
		return _Ad
	def reset_grid_position_state(self,data,product):data[_I][product]=_A;data[_J][product]=0
	def symmetric_grid_target(self,product,order_depth,current_position,data,threshold):
		best_bid,best_ask=self.best_bid_ask(order_depth);mid=self.mid_price(order_depth)
		if best_bid is _A and best_ask is _A and mid is _A:return current_position
		if product not in data[_H]or data[_H].get(product)is _A:data[_H][product]=float(mid if mid is not _A else best_ask if best_ask is not _A else best_bid);self.reset_grid_position_state(data,product)
		ref=float(data[_H][product]);entry=data[_I].get(product)
		if current_position>0:
			if entry is _A:entry=float(mid if mid is not _A else best_ask if best_ask is not _A else best_bid);data[_I][product]=entry;data[_J][product]=1
			if best_bid is not _A and best_bid>=float(entry)+threshold:data[_H][product]=float(best_bid);self.reset_grid_position_state(data,product);return 0
			return self.POSITION_LIMIT
		if current_position<0:
			if entry is _A:entry=float(mid if mid is not _A else best_bid if best_bid is not _A else best_ask);data[_I][product]=entry;data[_J][product]=-1
			if best_ask is not _A and best_ask<=float(entry)-threshold:data[_H][product]=float(best_ask);self.reset_grid_position_state(data,product);return 0
			return-self.POSITION_LIMIT
		self.reset_grid_position_state(data,product)
		if best_ask is not _A and best_ask<=ref-threshold:data[_I][product]=float(best_ask);data[_J][product]=1;return self.POSITION_LIMIT
		if best_bid is not _A and best_bid>=ref+threshold:data[_I][product]=float(best_bid);data[_J][product]=-1;return-self.POSITION_LIMIT
		return 0
	def reset_trend_state(self,data,product):data[_AQ][product]=0;data[_C][product]=_A;data[_F][product]=_A;data[_Y][product]=0
	def buffered_trend_target(self,data,product,od,current_position,desired_dir,cover_buffer,reentry_buffer):
		best_bid,best_ask=self.best_bid_ask(od);mid=self.mid_price(od)
		if best_bid is _A and best_ask is _A and mid is _A:return current_position
		active_dir=int(data[_AQ].get(product,0))
		if active_dir!=desired_dir:self.reset_trend_state(data,product);data[_AQ][product]=desired_dir
		if desired_dir==0:self.reset_trend_state(data,product);return 0
		entry_anchor=data[_C].get(product);exit_anchor=data[_F].get(product);paused_dir=int(data[_Y].get(product,0))
		if desired_dir>0:
			if current_position<0:return 0
			if current_position>0:
				if entry_anchor is _A:entry_anchor=float(best_ask if best_ask is not _A else mid);data[_C][product]=entry_anchor
				if best_bid is not _A and best_bid<=float(entry_anchor)-cover_buffer:data[_F][product]=float(best_bid);data[_C][product]=_A;data[_Y][product]=1;return 0
				return self.POSITION_LIMIT
			if paused_dir!=1 or exit_anchor is _A:data[_C][product]=float(best_ask if best_ask is not _A else mid);data[_F][product]=_A;data[_Y][product]=0;return self.POSITION_LIMIT
			if best_ask is not _A and best_ask<=float(exit_anchor)-reentry_buffer:data[_C][product]=float(best_ask);data[_F][product]=_A;data[_Y][product]=0;return self.POSITION_LIMIT
			return 0
		if desired_dir<0:
			if current_position>0:return 0
			if current_position<0:
				if entry_anchor is _A:entry_anchor=float(best_bid if best_bid is not _A else mid);data[_C][product]=entry_anchor
				if best_bid is not _A and best_bid>=float(entry_anchor)+cover_buffer:data[_F][product]=float(best_ask if best_ask is not _A else best_bid);data[_C][product]=_A;data[_Y][product]=-1;return 0
				return-self.POSITION_LIMIT
			if paused_dir!=-1 or exit_anchor is _A:data[_C][product]=float(best_bid if best_bid is not _A else mid);data[_F][product]=_A;data[_Y][product]=0;return-self.POSITION_LIMIT
			if best_bid is not _A and best_bid>=float(exit_anchor)+reentry_buffer:data[_C][product]=float(best_bid);data[_F][product]=_A;data[_Y][product]=0;return-self.POSITION_LIMIT
			return 0
		return 0
	def target_for_product(self,data,product,od,current_position,timestamp):
		mid=self.mid_price(od)
		if mid is _A:return current_position
		if product==self.ROBOT_DISHES:return self.symmetric_grid_target(product=product,order_depth=od,current_position=current_position,data=data,threshold=self.DISHES_GRID_THRESHOLD)
		if product==self.ROBOT_MOPPING:
			mode=self.update_mopping_laundry_mode(data,product,mid,timestamp)
			if mode==_M:return self.buffered_trend_target(data=data,product=product,od=od,current_position=current_position,desired_dir=1,cover_buffer=self.MOPPING_COVER_BUFFER,reentry_buffer=self.MOPPING_REENTRY_BUFFER)
			if mode==_N:return self.buffered_trend_target(data=data,product=product,od=od,current_position=current_position,desired_dir=-1,cover_buffer=self.MOPPING_COVER_BUFFER,reentry_buffer=self.MOPPING_REENTRY_BUFFER)
			return 0
		if product==self.ROBOT_LAUNDRY:
			mode=self.update_mopping_laundry_mode(data,product,mid,timestamp)
			if mode==_M:return self.buffered_trend_target(data=data,product=product,od=od,current_position=current_position,desired_dir=1,cover_buffer=self.LAUNDRY_COVER_BUFFER,reentry_buffer=self.LAUNDRY_REENTRY_BUFFER)
			if mode==_N:return self.buffered_trend_target(data=data,product=product,od=od,current_position=current_position,desired_dir=-1,cover_buffer=self.LAUNDRY_COVER_BUFFER,reentry_buffer=self.LAUNDRY_REENTRY_BUFFER)
			return 0
		if product==self.ROBOT_IRONING:
			mode=self.update_ironing_mode(data,product,mid)
			if mode==_M:return self.buffered_trend_target(data=data,product=product,od=od,current_position=current_position,desired_dir=1,cover_buffer=self.IRONING_COVER_BUFFER,reentry_buffer=self.IRONING_REENTRY_BUFFER)
			if mode==_N:return self.buffered_trend_target(data=data,product=product,od=od,current_position=current_position,desired_dir=-1,cover_buffer=self.IRONING_COVER_BUFFER,reentry_buffer=self.IRONING_REENTRY_BUFFER)
			return 0
		return 0
	def orders_to_target(self,product,od,current_position,target_position):
		orders=[];target_position=max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target_position));delta=target_position-current_position
		if delta==0:return orders
		sp=self.spread(od);reducing_risk=abs(target_position)<abs(current_position)
		if sp is not _A and sp>self.MAX_SPREAD_TO_OPEN and not reducing_risk:return orders
		if delta>0:
			need=min(delta,self.POSITION_LIMIT-current_position)
			for(ask,ask_volume)in sorted(od.sell_orders.items()):
				if need<=0:break
				available=-ask_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,ask,qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(od)
				if best_bid is not _A and best_ask is not _A:
					price=min(best_bid+1,best_ask-1)
					if price>best_bid:orders.append(Order(product,price,need))
				elif best_bid is not _A:orders.append(Order(product,best_bid+1,need))
				elif best_ask is not _A:orders.append(Order(product,best_ask,need))
		elif delta<0:
			need=min(-delta,self.POSITION_LIMIT+current_position)
			for(bid,bid_volume)in sorted(od.buy_orders.items(),reverse=_b):
				if need<=0:break
				available=bid_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,bid,-qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(od)
				if best_bid is not _A and best_ask is not _A:
					price=max(best_ask-1,best_bid+1)
					if price<best_ask:orders.append(Order(product,price,-need))
				elif best_ask is not _A:orders.append(Order(product,best_ask-1,-need))
				elif best_bid is not _A:orders.append(Order(product,best_bid,-need))
		return orders
	def run_with_data(self,state,trader_data):
		result={};data=self.load_data(trader_data,state.timestamp)
		for product in state.order_depths:result[product]=[]
		for(product,od)in state.order_depths.items():
			if product not in self.TRADED:continue
			mid=self.mid_price(od)
			if mid is _A:continue
			self.update_mid_state(data,product,mid);current_position=state.position.get(product,0);target_position=self.target_for_product(data=data,product=product,od=od,current_position=current_position,timestamp=state.timestamp);result[product]=self.orders_to_target(product=product,od=od,current_position=current_position,target_position=target_position)
		traderData=self.save_data(data);conversions=0;return result,conversions,traderData
class _MicrochipStrategy:
	POSITION_LIMIT=10;OVAL=_Ae;SQUARE=_B7;CIRCLE='MICROCHIP_CIRCLE';RECTANGLE=_As;TRIANGLE='MICROCHIP_TRIANGLE';TRADED={OVAL,SQUARE,CIRCLE};ALL_MICROCHIPS={OVAL,SQUARE,CIRCLE,RECTANGLE,TRIANGLE};VOL_ALPHA=.03;SPREAD_ALPHA=.05;FAST_ALPHA=.06;SLOW_ALPHA=.012;PARAMS={OVAL:{_G:'always_short',_d:18.,_e:2e1,_f:.025,_g:.55,_Af:90},SQUARE:{_G:_At,_r:1000,_s:25.,_t:25.,_u:.018,_h:.2,_v:3,_w:_B,_d:16.,_e:18.,_f:.015,_g:.55,_Af:140},CIRCLE:{_G:_At,_r:4000,_s:45.,_t:4e1,_u:.04,_h:.2,_v:5,_w:1.7,_d:38.,_e:35.,_f:.035,_g:.55,_B8:2.8,_Af:120}}
	def best_bid_ask(self,order_depth):best_bid=max(order_depth.buy_orders.keys())if order_depth.buy_orders else _A;best_ask=min(order_depth.sell_orders.keys())if order_depth.sell_orders else _A;return best_bid,best_ask
	def mid_price(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is not _A and best_ask is not _A:return(best_bid+best_ask)/2.
		if best_bid is not _A:return float(best_bid)
		if best_ask is not _A:return float(best_ask)
	def spread(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is _A or best_ask is _A:return
		return best_ask-best_bid
	def fresh_data(self):return{_D:{},_E:{},_U:{},_V:{},_Q:{},_O:{},_Z:{},_a:{},_P:{},_S:{},_A3:{},_C:{},_F:{},_A4:{},_A5:{}}
	def load_data(self,trader_data,timestamp):
		if timestamp==0:return self.fresh_data()
		if not trader_data:return self.fresh_data()
		try:data=json.loads(trader_data)
		except Exception:return self.fresh_data()
		defaults=self.fresh_data()
		for(key,value)in defaults.items():data.setdefault(key,value)
		return data
	def update_indicators(self,data,product,mid,spread):
		sp=float(spread if spread is not _A else _L)
		if product not in data[_D]:data[_D][product]=mid;data[_E][product]=mid;data[_U][product]=mid;data[_V][product]=mid;data[_Q][product]=_L;data[_O][product]=max(sp,_B);data[_Z][product]=1;data[_a][product]=0;data[_P][product]=0;data[_S][product]=0;return
		last_mid=float(data[_E].get(product,mid));abs_step=abs(mid-last_mid);old_vol=float(data[_Q].get(product,_L));old_spread=float(data[_O].get(product,max(sp,_B)));old_fast=float(data[_U].get(product,mid));old_slow=float(data[_V].get(product,mid));data[_Q][product]=self.VOL_ALPHA*abs_step+(_B-self.VOL_ALPHA)*old_vol;data[_O][product]=self.SPREAD_ALPHA*max(sp,_B)+(_B-self.SPREAD_ALPHA)*old_spread;data[_U][product]=self.FAST_ALPHA*mid+(_B-self.FAST_ALPHA)*old_fast;data[_V][product]=self.SLOW_ALPHA*mid+(_B-self.SLOW_ALPHA)*old_slow;data[_E][product]=mid;data[_Z][product]=int(data[_Z].get(product,0))+1
	def cover_threshold(self,data,product,mid):p=self.PARAMS[product];vol=max(float(data[_Q].get(product,_B)),_B);sp=max(float(data[_O].get(product,_B)),_B);return max(p[_d]*vol,p[_e]*sp,p[_f]*mid)
	def detection_threshold(self,data,product,mid):p=self.PARAMS[product];vol=max(float(data[_Q].get(product,_B)),_B);sp=max(float(data[_O].get(product,_B)),_B);return max(p[_s]*vol,p[_t]*sp,p[_u]*mid)
	def reset_directional_grid(self,data,product,direction):data[_A3][product]=direction;data[_C][product]=_A;data[_F][product]=_A;data[_A4][product]=0;data[_A5][product]=_A
	def detect_direction(self,data,product,mid):
		if product==self.OVAL:
			if int(data[_S].get(product,0))!=-1:data[_S][product]=-1;self.reset_directional_grid(data,product,-1)
			return-1
		confirmed=int(data[_S].get(product,0))
		if confirmed!=0:return confirmed
		p=self.PARAMS[product];count=int(data[_Z].get(product,0))
		if count<int(p[_r]):return 0
		init_mid=float(data[_D].get(product,mid));move=mid-init_mid;threshold=self.detection_threshold(data,product,mid);ema_fast=float(data[_U].get(product,mid));ema_slow=float(data[_V].get(product,mid));ema_gap=ema_fast-ema_slow;candidate=0
		if abs(move)>=p[_w]*threshold:
			if move>0 and ema_gap>p[_h]*threshold:candidate=1
			elif move<0 and ema_gap<-p[_h]*threshold:candidate=-1
		if candidate==0:data[_a][product]=0;data[_P][product]=0;return 0
		previous_raw=int(data[_a].get(product,0))
		if candidate==previous_raw:data[_P][product]=int(data[_P].get(product,0))+1
		else:data[_a][product]=candidate;data[_P][product]=1
		if int(data[_P].get(product,0))>=int(p[_v]):
			data[_S][product]=candidate;self.reset_directional_grid(data,product,candidate)
			if product==self.CIRCLE:
				cover=self.cover_threshold(data,product,mid)
				if abs(move)>p[_B8]*cover:data[_A4][product]=candidate;data[_A5][product]=mid
			return candidate
		return 0
	def directional_grid_target(self,data,product,order_depth,current_position,direction):
		best_bid,best_ask=self.best_bid_ask(order_depth);mid=self.mid_price(order_depth)
		if direction==0 or mid is _A or best_bid is _A and best_ask is _A:return 0
		if int(data[_A3].get(product,0))!=direction:self.reset_directional_grid(data,product,direction)
		cover=self.cover_threshold(data,product,mid);reentry=self.PARAMS[product][_g]*cover;wait_dir=int(data[_A4].get(product,0));wait_ref=data[_A5].get(product)
		if wait_dir==direction and wait_ref is not _A and current_position==0:
			wait_ref=float(wait_ref)
			if direction<0:
				if best_bid is not _A and best_bid>=wait_ref+reentry:data[_A4][product]=0;data[_A5][product]=_A;data[_C][product]=float(best_bid);return-self.POSITION_LIMIT
				return 0
			if direction>0:
				if best_ask is not _A and best_ask<=wait_ref-reentry:data[_A4][product]=0;data[_A5][product]=_A;data[_C][product]=float(best_ask);return self.POSITION_LIMIT
				return 0
		entry_anchor=data[_C].get(product);exit_anchor=data[_F].get(product)
		if direction<0:
			if current_position>0:return 0
			if current_position<0:
				if entry_anchor is _A:entry_anchor=float(best_bid if best_bid is not _A else mid);data[_C][product]=entry_anchor
				if best_bid is not _A and best_bid>=float(entry_anchor)+cover:data[_C][product]=_A;data[_F][product]=float(best_ask if best_ask is not _A else best_bid);return 0
				return-self.POSITION_LIMIT
			if exit_anchor is _A:data[_C][product]=float(best_bid if best_bid is not _A else mid);return-self.POSITION_LIMIT
			if best_bid is not _A and best_bid>=float(exit_anchor)+reentry:data[_C][product]=float(best_bid);data[_F][product]=_A;return-self.POSITION_LIMIT
			return 0
		if direction>0:
			if current_position<0:return 0
			if current_position>0:
				if entry_anchor is _A:entry_anchor=float(best_ask if best_ask is not _A else mid);data[_C][product]=entry_anchor
				if best_ask is not _A and best_ask<=float(entry_anchor)-cover:data[_C][product]=_A;data[_F][product]=float(best_bid if best_bid is not _A else best_ask);return 0
				return self.POSITION_LIMIT
			if exit_anchor is _A:data[_C][product]=float(best_ask if best_ask is not _A else mid);return self.POSITION_LIMIT
			if best_ask is not _A and best_ask<=float(exit_anchor)-reentry:data[_C][product]=float(best_ask);data[_F][product]=_A;return self.POSITION_LIMIT
			return 0
		return 0
	def orders_to_target(self,product,order_depth,current_position,target_position,max_spread):
		orders=[];target_position=max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target_position));delta=target_position-current_position
		if delta==0:return orders
		sp=self.spread(order_depth);reducing_risk=abs(target_position)<abs(current_position)
		if sp is not _A and sp>max_spread and not reducing_risk:return orders
		if delta>0:
			need=delta
			for(ask,ask_volume)in sorted(order_depth.sell_orders.items()):
				if need<=0:break
				available=-ask_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,ask,qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=min(best_bid+1,best_ask-1)
					if price>best_bid:orders.append(Order(product,price,need))
				elif best_bid is not _A:orders.append(Order(product,best_bid+1,need))
		elif delta<0:
			need=-delta
			for(bid,bid_volume)in sorted(order_depth.buy_orders.items(),reverse=_b):
				if need<=0:break
				available=bid_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,bid,-qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=max(best_ask-1,best_bid+1)
					if price<best_ask:orders.append(Order(product,price,-need))
				elif best_ask is not _A:orders.append(Order(product,best_ask-1,-need))
		return orders
	def run_with_data(self,state,trader_data):
		result={};data=self.load_data(trader_data,state.timestamp)
		for product in state.order_depths:result[product]=[]
		mids={};spreads={}
		for product in self.TRADED:
			if product not in state.order_depths:continue
			order_depth=state.order_depths[product];mid=self.mid_price(order_depth)
			if mid is _A:continue
			mids[product]=mid;spreads[product]=self.spread(order_depth);self.update_indicators(data,product,mid,spreads[product])
		for product in self.TRADED:
			if product not in state.order_depths or product not in mids:continue
			current_position=state.position.get(product,0);direction=self.detect_direction(data,product,mids[product]);target=self.directional_grid_target(data=data,product=product,order_depth=state.order_depths[product],current_position=current_position,direction=direction);max_spread=int(self.PARAMS[product][_Af]);result[product]=self.orders_to_target(product=product,order_depth=state.order_depths[product],current_position=current_position,target_position=target,max_spread=max_spread)
		traderData=json.dumps(data,separators=(_i,_j));conversions=0;return result,conversions,traderData
class _OxygenShakeStrategy:
	POSITION_LIMIT=10;CHOCOLATE=_Au;EVENING=_Av;GARLIC=_Aw;MINT='OXYGEN_SHAKE_MINT';MORNING='OXYGEN_SHAKE_MORNING_BREATH';TRADED=[CHOCOLATE,EVENING,GARLIC,MINT,MORNING];VOL_ALPHA=.03;SPREAD_ALPHA=.05;FAST_ALPHA=.06;SLOW_ALPHA=.012;PARAMS={GARLIC:{_G:'fixed_long',_d:18.,_e:12.,_f:.012,_g:.55,_A6:5.5,_A7:8e1},CHOCOLATE:{_G:_At,_r:1000,_s:2e1,_t:2e1,_u:.018,_h:.18,_w:.8,_v:3,_d:16.,_e:16.,_f:.014,_g:.55,_A6:5.5,_A7:9e1},EVENING:{_G:_Az,_A1:MORNING,_r:1500,_s:28.,_t:28.,_u:.03,_h:.2,_w:1.6,_v:4,_Ax:.45,_Ay:.05,_d:2e1,_e:2e1,_f:.05,_g:.55,_A6:6.,_A7:1e2},MORNING:{_G:_Az,_A1:EVENING,_r:1500,_s:28.,_t:28.,_u:.03,_h:.2,_w:1.6,_v:4,_Ax:.45,_Ay:.05,_d:2e1,_e:2e1,_f:.05,_g:.55,_A6:6.,_A7:1e2},MINT:{_G:'neutral_grid',_B9:36.,_BA:26.,'grid_pct':.018,_BB:.9,_BC:3.5,_AR:.001,_A_:250,_A6:5.,_A7:9e1}}
	def best_bid_ask(self,order_depth):best_bid=max(order_depth.buy_orders.keys())if order_depth.buy_orders else _A;best_ask=min(order_depth.sell_orders.keys())if order_depth.sell_orders else _A;return best_bid,best_ask
	def mid_price(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is not _A and best_ask is not _A:return(best_bid+best_ask)/2.
		if best_bid is not _A:return float(best_bid)
		if best_ask is not _A:return float(best_ask)
	def spread(self,order_depth):
		best_bid,best_ask=self.best_bid_ask(order_depth)
		if best_bid is _A or best_ask is _A:return
		return best_ask-best_bid
	def fresh_data(self):return{_D:{},_E:{},_U:{},_V:{},_Q:{},_O:{},_Z:{},_a:{},_P:{},_S:{},_A3:{},_C:{},_F:{},_W:{},_T:{},_o:{},_A8:{}}
	def load_data(self,trader_data,timestamp):
		if timestamp==0:return self.fresh_data()
		if not trader_data:return self.fresh_data()
		try:data=json.loads(trader_data)
		except Exception:return self.fresh_data()
		defaults=self.fresh_data()
		for(key,value)in defaults.items():data.setdefault(key,value)
		return data
	def update_indicators(self,data,product,mid,spread):
		sp=float(spread if spread is not _A else _L)
		if product not in data[_D]:data[_D][product]=mid;data[_E][product]=mid;data[_U][product]=mid;data[_V][product]=mid;data[_Q][product]=_L;data[_O][product]=max(sp,_B);data[_Z][product]=1;data[_a][product]=0;data[_P][product]=0;data[_S][product]=0;return
		last_mid=float(data[_E].get(product,mid));abs_step=abs(mid-last_mid);old_vol=float(data[_Q].get(product,_L));old_spread=float(data[_O].get(product,max(sp,_B)));old_fast=float(data[_U].get(product,mid));old_slow=float(data[_V].get(product,mid));data[_Q][product]=self.VOL_ALPHA*abs_step+(_B-self.VOL_ALPHA)*old_vol;data[_O][product]=self.SPREAD_ALPHA*max(sp,_B)+(_B-self.SPREAD_ALPHA)*old_spread;data[_U][product]=self.FAST_ALPHA*mid+(_B-self.FAST_ALPHA)*old_fast;data[_V][product]=self.SLOW_ALPHA*mid+(_B-self.SLOW_ALPHA)*old_slow;data[_E][product]=mid;data[_Z][product]=int(data[_Z].get(product,0))+1
	def detection_threshold(self,data,product,mid):p=self.PARAMS[product];vol=max(float(data[_Q].get(product,_B)),_B);sp=max(float(data[_O].get(product,_B)),_B);return max(p[_s]*vol,p[_t]*sp,p[_u]*mid)
	def cover_threshold(self,data,product,mid):p=self.PARAMS[product];vol=max(float(data[_Q].get(product,_B)),_B);sp=max(float(data[_O].get(product,_B)),_B);return max(p[_d]*vol,p[_e]*sp,p[_f]*mid)
	def mint_grid_threshold(self,data,mid):p=self.PARAMS[self.MINT];vol=max(float(data[_Q].get(self.MINT,_B)),_B);sp=max(float(data[_O].get(self.MINT,_B)),_B);return max(p[_B9]*vol,p[_BA]*sp,p['grid_pct']*mid)
	def spread_allowed(self,data,product):p=self.PARAMS[product];sp=max(float(data[_O].get(product,_B)),_B);return max(float(p[_A7]),float(p[_A6])*sp)
	def reset_directional_grid(self,data,product,direction):data[_A3][product]=direction;data[_C][product]=_A;data[_F][product]=_A
	def pair_confirms(self,data,product,direction,pair,pair_mid):
		p=self.PARAMS[product]
		if pair not in data[_D]:return False
		pair_move=pair_mid-float(data[_D].get(pair,pair_mid));pair_gap=float(data[_U].get(pair,pair_mid))-float(data[_V].get(pair,pair_mid));pair_threshold=self.detection_threshold(data,pair,pair_mid);move_ok=direction*pair_move<=-float(p[_Ax])*pair_threshold;gap_ok=direction*pair_gap<=-float(p[_Ay])*pair_threshold;return move_ok and gap_ok
	def detect_direction(self,data,product,mids):
		if product==self.GARLIC:
			if int(data[_S].get(product,0))!=1:data[_S][product]=1;self.reset_directional_grid(data,product,1)
			return 1
		confirmed=int(data[_S].get(product,0))
		if confirmed!=0:return confirmed
		if product not in mids:return 0
		p=self.PARAMS[product];count=int(data[_Z].get(product,0))
		if count<int(p[_r]):return 0
		mid=mids[product];init_mid=float(data[_D].get(product,mid));move=mid-init_mid;threshold=self.detection_threshold(data,product,mid);ema_fast=float(data[_U].get(product,mid));ema_slow=float(data[_V].get(product,mid));ema_gap=ema_fast-ema_slow;candidate=0
		if abs(move)>=float(p[_w])*threshold:
			if move>0 and ema_gap>float(p[_h])*threshold:candidate=1
			elif move<0 and ema_gap<-float(p[_h])*threshold:candidate=-1
		if candidate!=0 and p[_G]==_Az:
			pair=p[_A1]
			if pair not in mids or not self.pair_confirms(data,product,candidate,pair,mids[pair]):candidate=0
		if candidate==0:data[_a][product]=0;data[_P][product]=0;return 0
		previous_raw=int(data[_a].get(product,0))
		if candidate==previous_raw:data[_P][product]=int(data[_P].get(product,0))+1
		else:data[_a][product]=candidate;data[_P][product]=1
		if int(data[_P].get(product,0))>=int(p[_v]):data[_S][product]=candidate;self.reset_directional_grid(data,product,candidate);return candidate
		return 0
	def directional_grid_target(self,data,product,order_depth,current_position,direction):
		best_bid,best_ask=self.best_bid_ask(order_depth);mid=self.mid_price(order_depth)
		if direction==0 or mid is _A or best_bid is _A and best_ask is _A:return 0
		if int(data[_A3].get(product,0))!=direction:self.reset_directional_grid(data,product,direction)
		cover=self.cover_threshold(data,product,mid);reentry=float(self.PARAMS[product][_g])*cover;entry_anchor=data[_C].get(product);exit_anchor=data[_F].get(product)
		if direction<0:
			if current_position>0:return 0
			if current_position<0:
				if entry_anchor is _A:entry_anchor=float(best_bid if best_bid is not _A else mid);data[_C][product]=entry_anchor
				if best_bid is not _A and best_bid>=float(entry_anchor)+cover:data[_C][product]=_A;data[_F][product]=float(best_ask if best_ask is not _A else best_bid);return 0
				return-self.POSITION_LIMIT
			if exit_anchor is _A:data[_C][product]=float(best_bid if best_bid is not _A else mid);return-self.POSITION_LIMIT
			if best_bid is not _A and best_bid>=float(exit_anchor)+reentry:data[_C][product]=float(best_bid);data[_F][product]=_A;return-self.POSITION_LIMIT
			return 0
		if direction>0:
			if current_position<0:return 0
			if current_position>0:
				if entry_anchor is _A:entry_anchor=float(best_ask if best_ask is not _A else mid);data[_C][product]=entry_anchor
				if best_ask is not _A and best_ask<=float(entry_anchor)-cover:data[_C][product]=_A;data[_F][product]=float(best_bid if best_bid is not _A else best_ask);return 0
				return self.POSITION_LIMIT
			if exit_anchor is _A:data[_C][product]=float(best_ask if best_ask is not _A else mid);return self.POSITION_LIMIT
			if best_ask is not _A and best_ask<=float(exit_anchor)-reentry:data[_C][product]=float(best_ask);data[_F][product]=_A;return self.POSITION_LIMIT
			return 0
		return 0
	def neutral_grid_target(self,data,order_depth,current_position):
		product=self.MINT;p=self.PARAMS[product];best_bid,best_ask=self.best_bid_ask(order_depth);mid=self.mid_price(order_depth)
		if mid is _A or best_bid is _A and best_ask is _A:return 0
		if product not in data[_W]or data[_W].get(product)is _A:data[_W][product]=mid;data[_T][product]=_A;data[_o][product]=0;data[_A8][product]=0
		ref=float(data[_W].get(product,mid));threshold=self.mint_grid_threshold(data,mid);exit_threshold=float(p[_BB])*threshold;stop_threshold=float(p[_BC])*threshold
		if current_position==0:
			cooldown=int(data[_A8].get(product,0))
			if cooldown>0:
				data[_A8][product]=cooldown-1;data[_W][product]=float(p[_AR])*mid+(_B-float(p[_AR]))*ref
				if abs(mid-ref)>.5*threshold:return 0
			if best_ask is not _A and best_ask<=ref-threshold:data[_T][product]=float(best_ask);data[_o][product]=1;return self.POSITION_LIMIT
			if best_bid is not _A and best_bid>=ref+threshold:data[_T][product]=float(best_bid);data[_o][product]=-1;return-self.POSITION_LIMIT
			data[_W][product]=float(p[_AR])*mid+(_B-float(p[_AR]))*ref;return 0
		if current_position>0:
			entry=data[_T].get(product)
			if entry is _A:entry=float(best_ask if best_ask is not _A else mid);data[_T][product]=entry
			if best_bid is not _A and best_bid>=float(entry)+exit_threshold:data[_W][product]=float(best_bid);data[_T][product]=_A;data[_o][product]=0;return 0
			if best_ask is not _A and best_ask<=float(entry)-stop_threshold:data[_W][product]=mid;data[_T][product]=_A;data[_o][product]=0;data[_A8][product]=int(p[_A_]);return 0
			return self.POSITION_LIMIT
		if current_position<0:
			entry=data[_T].get(product)
			if entry is _A:entry=float(best_bid if best_bid is not _A else mid);data[_T][product]=entry
			if best_ask is not _A and best_ask<=float(entry)-exit_threshold:data[_W][product]=float(best_ask);data[_T][product]=_A;data[_o][product]=0;return 0
			if best_bid is not _A and best_bid>=float(entry)+stop_threshold:data[_W][product]=mid;data[_T][product]=_A;data[_o][product]=0;data[_A8][product]=int(p[_A_]);return 0
			return-self.POSITION_LIMIT
		return 0
	def orders_to_target(self,product,order_depth,current_position,target_position,max_spread):
		orders=[];target_position=max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target_position));delta=target_position-current_position
		if delta==0:return orders
		sp=self.spread(order_depth);reducing_risk=abs(target_position)<abs(current_position)
		if sp is not _A and float(sp)>max_spread and not reducing_risk:return orders
		if delta>0:
			need=delta
			for(ask,ask_volume)in sorted(order_depth.sell_orders.items()):
				if need<=0:break
				available=-ask_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,ask,qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=min(best_bid+1,best_ask-1)
					if price>best_bid:orders.append(Order(product,price,need))
				elif best_bid is not _A:orders.append(Order(product,best_bid+1,need))
		elif delta<0:
			need=-delta
			for(bid,bid_volume)in sorted(order_depth.buy_orders.items(),reverse=_b):
				if need<=0:break
				available=bid_volume
				if available<=0:continue
				qty=min(need,available);orders.append(Order(product,bid,-qty));need-=qty
			if need>0:
				best_bid,best_ask=self.best_bid_ask(order_depth)
				if best_bid is not _A and best_ask is not _A:
					price=max(best_ask-1,best_bid+1)
					if price<best_ask:orders.append(Order(product,price,-need))
				elif best_ask is not _A:orders.append(Order(product,best_ask-1,-need))
		return orders
	def run_with_data(self,state,trader_data):
		result={};data=self.load_data(trader_data,state.timestamp)
		for product in state.order_depths:result[product]=[]
		mids={};spreads={}
		for product in self.TRADED:
			if product not in state.order_depths:continue
			order_depth=state.order_depths[product];mid=self.mid_price(order_depth)
			if mid is _A:continue
			spread=self.spread(order_depth);mids[product]=mid;spreads[product]=spread;self.update_indicators(data,product,mid,spread)
		for product in self.TRADED:
			if product not in state.order_depths or product not in mids:continue
			current_position=state.position.get(product,0);order_depth=state.order_depths[product]
			if product==self.MINT:target=self.neutral_grid_target(data,order_depth,current_position)
			else:direction=self.detect_direction(data,product,mids);target=self.directional_grid_target(data=data,product=product,order_depth=order_depth,current_position=current_position,direction=direction)
			result[product]=self.orders_to_target(product=product,order_depth=order_depth,current_position=current_position,target_position=target,max_spread=self.spread_allowed(data,product))
		traderData=json.dumps(data,separators=(_i,_j));conversions=0;return result,conversions,traderData
class Trader:
	POSITION_LIMIT=10;OPEN_TARGETS={_AW:10,_B0:-10,_BD:10,_BE:-10,_AV:-10,_BF:10,_Ap:10,_As:-10,_BG:-10,_Ao:-10,_Am:10,_Ae:-10,_BH:10,_BI:10,_AK:-10,_Ar:10,_Aw:-10,_B5:-10,_Av:10,_Ak:10,_Al:-10,_B7:-10,_Au:-5};MID_TARGETS={_An:-10,_AW:10,_Ap:10,_BD:10,_AK:10,_As:-10,_BE:-10,_BF:10,_Aq:-10,'TRANSLATOR_ECLIPSE_CHARCOAL':10,_AV:-10,_B0:-10,_BG:-10,_Ao:-10,_Ae:-10,_BH:10,_BI:10,_Am:10};GATE_20K={_BJ:(-1,1e2)};GATE_50K={'PANEL_1X4':(-1,8e1),'TRANSLATOR_SPACE_GRAY':(-1,1e2),_B4:(1,1e2),_AU:(-1,1e2),_BK:(1,1e2),'TRANSLATOR_ASTRO_BLACK':(1,15e1)};LATE_TARGETS={_Ae:-10,_Ah:-10,_Aw:10,_AK:10,_B0:-10,_BJ:10,_AU:-10,_BK:10,_Aj:-7,_Ak:7,_B3:5,_Ai:-4};T_GATE_20=20000;T_GATE_50=50000;T_LATE=100000;PEBBLES=[_Ah,_AU,_AV,_B1,_AW];SNACK_PAIR_1=_Ai,_B2;SNACK_PAIR_2=_Aj,_Al;MR_PRODUCTS={_Ar,_Aq,_Av,_Au};PEBBLES_OVERRIDE_PRODUCTS=set(_PebblesStrategy.TRADED);SNACKPACK_OVERRIDE_PRODUCTS=set(_SnackpackStrategy.TRADED);SLEEP_POD_OVERRIDE_PRODUCTS=set(_SleepPodStrategy.PRODUCTS);GALAXY_OVERRIDE_PRODUCTS=set(_GalaxyStrategy.GALAXY_PRODUCTS);ROBOT_OVERRIDE_PRODUCTS=set(_RobotStrategy.TRADED);MICROCHIP_OVERRIDE_PRODUCTS=set(_MicrochipStrategy.ALL_MICROCHIPS);OXYGEN_SHAKE_OVERRIDE_PRODUCTS=set(_OxygenShakeStrategy.TRADED);OVERRIDE_PRODUCTS=PEBBLES_OVERRIDE_PRODUCTS|SNACKPACK_OVERRIDE_PRODUCTS|SLEEP_POD_OVERRIDE_PRODUCTS|GALAXY_OVERRIDE_PRODUCTS|ROBOT_OVERRIDE_PRODUCTS|MICROCHIP_OVERRIDE_PRODUCTS|OXYGEN_SHAKE_OVERRIDE_PRODUCTS
	def bid(self):return 15
	def load_data(self,trader_data):
		if not trader_data:return{_D:{},_AS:{},_AT:{},_A9:{},_AA:{},_AB:{},_E:{},_x:{},_Ag:{}}
		try:data=json.loads(trader_data)
		except Exception:data={_D:{},_AS:{},_AT:{},_A9:{},_AA:{},_AB:{},_E:{},_x:{},_Ag:{}}
		data.setdefault(_D,{});data.setdefault(_AS,{});data.setdefault(_AT,{});data.setdefault(_A9,{});data.setdefault(_AA,{});data.setdefault(_AB,{});data.setdefault(_E,{});data.setdefault(_x,{});data.setdefault(_Ag,{});return data
	def save_data(self,data):return json.dumps(data,separators=(_i,_j))
	def best_bid(self,order_depth):
		if not order_depth.buy_orders:return
		return max(order_depth.buy_orders.keys())
	def best_ask(self,order_depth):
		if not order_depth.sell_orders:return
		return min(order_depth.sell_orders.keys())
	def mid_price(self,order_depth):
		bid=self.best_bid(order_depth);ask=self.best_ask(order_depth)
		if bid is not _A and ask is not _A:return(bid+ask)/2.
		if bid is not _A:return float(bid)
		if ask is not _A:return float(ask)
	def spread(self,order_depth):
		bid=self.best_bid(order_depth);ask=self.best_ask(order_depth)
		if bid is _A or ask is _A:return
		return ask-bid
	def store_init_mid(self,data,product,mid):
		if product not in data[_D]:data[_D][product]=mid
	def update_micro_stats(self,data,product,mid):
		last=data[_E].get(product)
		if last is _A:data[_E][product]=mid;data[_x][product]=_B;return
		delta=mid-last;prev_abs=data[_x].get(product,abs(delta));data[_x][product]=.95*prev_abs+.05*abs(delta);data[_E][product]=mid
	def update_pair_stat(self,data,key,value):
		count=int(data[_AB].get(key,0));mean=float(data[_A9].get(key,value));var=float(data[_AA].get(key,1e4));alpha=.003
		if count==0:mean=value;var=1e4
		else:diff=value-mean;mean=(_B-alpha)*mean+alpha*value;var=(_B-alpha)*var+alpha*diff*diff
		data[_AB][key]=count+1;data[_A9][key]=mean;data[_AA][key]=max(var,_B)
	def eval_gate_once(self,data,gate_store,product,mid,gate_config):
		if product not in gate_config:return
		if product in data[gate_store]:return
		init=data[_D].get(product)
		if init is _A:data[gate_store][product]=0;return
		direction,threshold=gate_config[product];favorable_move=direction*(mid-init)
		if favorable_move>=threshold:data[gate_store][product]=direction
		else:data[gate_store][product]=0
	def pebble_arb_targets(self,mids,order_depths,base_targets):
		out={}
		if not all(p in mids and p in order_depths for p in self.PEBBLES):return out
		total=sum(mids[p]for p in self.PEBBLES);residual=total-5e4
		if abs(residual)<12.:return out
		best_product=_A;best_direction=0;best_edge=_L
		for p in self.PEBBLES:
			od=order_depths[p];bid=self.best_bid(od);ask=self.best_ask(od);sp=self.spread(od)
			if bid is _A or ask is _A or sp is _A:continue
			fv=5e4-sum(mids[q]for q in self.PEBBLES if q!=p);tau=.5*sp+_B;buy_edge=fv-ask-tau;sell_edge=bid-fv-tau
			if buy_edge>best_edge:best_edge=buy_edge;best_product=p;best_direction=1
			if sell_edge>best_edge:best_edge=sell_edge;best_product=p;best_direction=-1
		if best_product is _A or best_edge<=0:return out
		base=base_targets.get(best_product,0)
		if base!=0 and(base>0)!=(best_direction>0):return out
		if base==0:out[best_product]=6*best_direction
		else:out[best_product]=base
		return out
	def snack_pair_targets(self,data,mids,base_targets):
		out={};pairs={'CV':self.SNACK_PAIR_1,'PR':self.SNACK_PAIR_2}
		for(key,pair)in pairs.items():
			a,b=pair
			if a not in mids or b not in mids:continue
			s=mids[a]+mids[b];count=int(data[_AB].get(key,0));mean=float(data[_A9].get(key,s));var=float(data[_AA].get(key,1e4));sd=math.sqrt(max(var,_B));self.update_pair_stat(data,key,s)
			if count<200:continue
			z=(s-mean)/sd
			if abs(z)<2.2:continue
			direction=-1 if z>0 else 1;size=3
			if abs(z)>3.:size=5
			for p in pair:
				if base_targets.get(p,0)!=0:continue
				out[p]=direction*size
		return out
	def base_target_for_product(self,data,product,mid,timestamp):
		if timestamp>=self.T_LATE:return self.LATE_TARGETS.get(product,0)
		if product in self.GATE_20K:
			if mid is not _A and timestamp>=self.T_GATE_20:self.eval_gate_once(data,_AS,product,mid,self.GATE_20K)
			direction=data[_AS].get(product)
			if direction is _A:return 0
			return int(direction)*self.POSITION_LIMIT
		if product in self.GATE_50K:
			if timestamp<self.T_GATE_50:return 0
			if mid is not _A:self.eval_gate_once(data,_AT,product,mid,self.GATE_50K)
			direction=data[_AT].get(product)
			if direction is _A:return 0
			return int(direction)*self.POSITION_LIMIT
		if timestamp<self.T_GATE_50:return self.OPEN_TARGETS.get(product,0)
		return self.MID_TARGETS.get(product,0)
	def send_to_target(self,product,order_depth,current_pos,target_pos):
		orders=[];target_pos=max(-self.POSITION_LIMIT,min(self.POSITION_LIMIT,target_pos));delta=target_pos-current_pos
		if delta==0:return orders
		sp=self.spread(order_depth);reducing_risk=abs(target_pos)<abs(current_pos)
		if sp is not _A and sp>150 and not reducing_risk:return orders
		if delta>0:
			qty_needed=delta
			for(ask,ask_volume)in sorted(order_depth.sell_orders.items()):
				if qty_needed<=0:break
				available=-ask_volume
				if available<=0:continue
				qty=min(qty_needed,available);orders.append(Order(product,ask,qty));qty_needed-=qty
			if qty_needed>0:
				bid=self.best_bid(order_depth);ask=self.best_ask(order_depth)
				if bid is not _A and ask is not _A and bid+1<ask:orders.append(Order(product,bid+1,qty_needed))
				elif bid is not _A:orders.append(Order(product,bid,qty_needed))
		elif delta<0:
			qty_needed=-delta
			for(bid,bid_volume)in sorted(order_depth.buy_orders.items(),reverse=_b):
				if qty_needed<=0:break
				available=bid_volume
				if available<=0:continue
				qty=min(qty_needed,available);orders.append(Order(product,bid,-qty));qty_needed-=qty
			if qty_needed>0:
				bid=self.best_bid(order_depth);ask=self.best_ask(order_depth)
				if bid is not _A and ask is not _A and bid+1<ask:orders.append(Order(product,ask-1,-qty_needed))
				elif ask is not _A:orders.append(Order(product,ask,-qty_needed))
		return orders
	def passive_mean_reversion_orders(self,product,order_depth,current_pos,base_target,data):
		orders=[]
		if product not in self.MR_PRODUCTS:return orders
		if base_target!=0:return orders
		if abs(current_pos)>=6:return orders
		bid=self.best_bid(order_depth);ask=self.best_ask(order_depth)
		if bid is _A or ask is _A:return orders
		mid=(bid+ask)/2.;last=data[_E].get(product)
		if last is _A:return orders
		delta=mid-last;avg_abs=float(data[_x].get(product,_B));threshold=max(3.,2.5*avg_abs)
		if delta>threshold and current_pos>-6:
			price=ask-1
			if price>bid:
				qty=min(2,self.POSITION_LIMIT+current_pos)
				if qty>0:orders.append(Order(product,price,-qty))
		elif delta<-threshold and current_pos<6:
			price=bid+1
			if price<ask:
				qty=min(2,self.POSITION_LIMIT-current_pos)
				if qty>0:orders.append(Order(product,price,qty))
		return orders
	def override_strategy_orders(self,state,data):
		override_orders={product:[]for product in state.order_depths if product in self.OVERRIDE_PRODUCTS};substates=data.setdefault(_Ag,{});strategies=[('pebbles',_PebblesStrategy(),self.PEBBLES_OVERRIDE_PRODUCTS),('snackpack',_SnackpackStrategy(),self.SNACKPACK_OVERRIDE_PRODUCTS),('sleep_pods',_SleepPodStrategy(),self.SLEEP_POD_OVERRIDE_PRODUCTS),('galaxy',_GalaxyStrategy(),self.GALAXY_OVERRIDE_PRODUCTS),('robot',_RobotStrategy(),self.ROBOT_OVERRIDE_PRODUCTS),('microchip',_MicrochipStrategy(),self.MICROCHIP_OVERRIDE_PRODUCTS),('oxygen_shake',_OxygenShakeStrategy(),self.OXYGEN_SHAKE_OVERRIDE_PRODUCTS)]
		for(key,strategy,traded_products)in strategies:
			trader_data=substates.get(key,'');orders,_conversions,new_trader_data=strategy.run_with_data(state=state,trader_data=trader_data);substates[key]=new_trader_data
			for product in traded_products:
				if product in state.order_depths:override_orders[product]=orders.get(product,[])
		return override_orders
	def run(self,state):
		result={};data=self.load_data(state.traderData);override_orders=self.override_strategy_orders(state,data);mids={};base_targets={}
		for(product,order_depth)in state.order_depths.items():
			mid=self.mid_price(order_depth)
			if mid is not _A:mids[product]=mid;self.store_init_mid(data,product,mid)
			base_targets[product]=self.base_target_for_product(data=data,product=product,mid=mid,timestamp=state.timestamp)
		pebble_targets=self.pebble_arb_targets(mids=mids,order_depths=state.order_depths,base_targets=base_targets);snack_targets=self.snack_pair_targets(data=data,mids=mids,base_targets=base_targets)
		for(product,order_depth)in state.order_depths.items():
			mid=mids.get(product)
			if mid is not _A:self.update_micro_stats(data,product,mid)
			if product in override_orders:result[product]=override_orders.get(product,[]);continue
			target_pos=base_targets.get(product,0)
			if product in pebble_targets:target_pos=pebble_targets[product]
			if target_pos==0 and product in snack_targets:target_pos=snack_targets[product]
			current_pos=state.position.get(product,0);orders=self.send_to_target(product=product,order_depth=order_depth,current_pos=current_pos,target_pos=target_pos)
			if target_pos==0:orders.extend(self.passive_mean_reversion_orders(product=product,order_depth=order_depth,current_pos=current_pos,base_target=target_pos,data=data))
			result[product]=orders
		traderData=self.save_data(data);conversions=0;return result,conversions,traderData