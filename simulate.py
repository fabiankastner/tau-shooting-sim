import pandas as pd
import numpy as np
import random
import dice
import math
from tqdm import tqdm


DEFENDERS_DF = pd.read_csv("marcos_degenerates.csv", na_values=None)
DEFENDERS_DF = DEFENDERS_DF.fillna(np.nan).replace([np.nan], [None])

WEAPON_PROFILES_DF = pd.read_csv("weapon_profiles.csv", na_values=None)
WEAPON_PROFILES_DF = WEAPON_PROFILES_DF.fillna(np.nan).replace([np.nan], [None])

FILE_PATH = "results.txt"



def pprint_to_file(txt):
    with open(FILE_PATH, 'a') as f:
        f.write(txt + '\n')

def strengh_vs_toughness(s, t):
    if s<=t//2:
        return 6
    elif s<t:
        return 5
    elif s==t:
        return 4
    elif s>t:
        return 3
    elif s>=t*2:
        return 2

def n_d6(n):
    results = list(dice.roll(f'{n}d6'))
    return results

def n_d6_higher_than(n, m):
    results = dice.roll(f'{n}d6')
    return sum([v>=m for v in list(results)])

def reroll_1(results, threshold):
    return n_d6_higher_than(sum([r==1 for r in results]), threshold)

def reroll(results, threshold):
    return n_d6_higher_than(sum([r<threshold for r in results]), threshold)



class WeaponProfile():
    def __init__(self, unit_name, weapon_profile_name, n, a, bs, s, ap, d, abilities):
        self.unit_name = unit_name
        self.weapon_profile_name = weapon_profile_name
        self.n = n
        self.a = a
        self.bs = bs
        self.s = s
        self.ap = ap
        self.d = d
        self.abilities = [] if not abilities else abilities.split(';')

class Unit():
    def __init__(self, unit_name, vehicle_or_monster, n_models, t, sv, w, iv, feel_no_pain, abilities):
        self.unit_name = unit_name
        self.is_vehicle_or_monster = vehicle_or_monster
        self.n_models = n_models
        self.t = t
        self.sv = sv
        self.w = w
        self.iv = iv
        self.feel_no_pain = feel_no_pain
        self.abilities = [] if not abilities else abilities.split(';')
        self.wounds = self.n_models * [self.w]



    def be_shot_at(self, weapon_profile):

        # hit
        hits = n_d6(weapon_profile.a*weapon_profile.n)
        n_hits = sum([h >= weapon_profile.bs for h in hits])

        if 'reroll_hit' in weapon_profile.abilities:
            n_hits += reroll(hits, weapon_profile.bs)
        elif 'reroll_hit_1' in weapon_profile.abilities:
            n_hits += reroll_1(hits, weapon_profile.bs)



        # wound
        wounds = n_d6(n_hits)
        t_threshold = strengh_vs_toughness(weapon_profile.s, self.t)
        n_wounds = sum([w >= t_threshold for w in wounds])

        if 'reroll_wound' in weapon_profile.abilities or ('reroll_wound_vm' in weapon_profile.abilities and self.is_vehicle_or_monster):
            n_wounds += reroll(wounds, t_threshold)
        elif 'reroll_wound_1' in weapon_profile.abilities:
            n_wounds += reroll_1(wounds, t_threshold)

        assert n_wounds<=len(wounds) and n_wounds<=n_hits


        # save
        if 'dev_wounds' in weapon_profile.abilities:
            not_saved = n_wounds
        else:
            not_saved = 0
            n_saves = 0
            if 'crit_ap_3' in weapon_profile.abilities:
                n_crits = sum([w==6 for w in wounds])
                save = self.sv + 3
                if self.iv and self.iv <  save:
                    save = self.iv
                not_saved_crits = n_crits - n_d6_higher_than(n_crits, save)
                n_saves += n_crits - not_saved_crits

                n_not_crits = sum([w!=6 for w in wounds])
                save_threshold = self.sv + weapon_profile.ap
                if self.iv and self.iv <  save_threshold:
                    save_threshold = self.iv
                n_saves = n_d6_higher_than(n_not_crits, save_threshold)
                n_saves += n_saves
                not_saved_normal = n_not_crits - n_saves 
                not_saved = not_saved_normal + not_saved_crits

            else:
                if 'nvm_ap+1' in weapon_profile.abilities:
                    if not self.is_vehicle_or_monster:
                        weapon_profile.ap += 1

                save_threshold = self.sv + weapon_profile.ap
                if self.iv and self.iv <  save_threshold:
                    save_threshold = self.iv
                saves = n_d6(n_wounds)

                if 'reroll_sv_1' in self.abilities:
                    rerolled_saves = n_d6(len([s for s in saves if s==1]))
                    saves = [s for s in saves if s>1] + rerolled_saves
                
                n_saves = len([s for s in saves if s>=save_threshold])
                not_saved += n_wounds - n_saves

            assert n_saves + not_saved == n_wounds



        # damage
        if type(weapon_profile.d)==int:
            damage = not_saved * [weapon_profile.d]
        else:
            modifier = 0
            if '+' in weapon_profile.d:
                modifier = int(weapon_profile.d.split('+')[-1])
            damage = list(n_d6(not_saved))
            if 'reroll_d_vm' in weapon_profile.abilities and self.is_vehicle_or_monster:
                damage_high = [d for d in damage if d>3]
                damage_low = [d for d in damage if d<3]
                damage_low_rerolled = n_d6(len(damage_low))
                damage = damage_high + damage_low_rerolled
            damage = [d + modifier for d in damage]


        # feel no pain
        for d in damage: 
            if not self.wounds:
                break
            if self.feel_no_pain:
                d -= n_d6_higher_than(d, self.feel_no_pain)

            if 'legendary_tenacity' in self.abilities:
                d = math.ceil(d/2)

            self.wounds[-1] -= d
            if self.wounds[-1] <= 0:
                del self.wounds[-1]
        
        return self.wounds



def _simulate(defender_name, attacker_profile, guided, stealth_suits_rerolls, retaliation_cadre, repeats):

    global WEAPON_PROFILES_DF
    WEAPON_PROFILES_DF_COPY = WEAPON_PROFILES_DF.copy()

    if guided:
        WEAPON_PROFILES_DF_COPY.bs = WEAPON_PROFILES_DF_COPY.bs-1
    if stealth_suits_rerolls:
        WEAPON_PROFILES_DF_COPY['abilities'] = WEAPON_PROFILES_DF_COPY['abilities'].astype(str) + ';reroll_wound_1;reroll_hit_1'
    if retaliation_cadre[0]:
        WEAPON_PROFILES_DF_COPY.s = WEAPON_PROFILES_DF_COPY.s+1
    if retaliation_cadre[1]:
        WEAPON_PROFILES_DF_COPY.ap = WEAPON_PROFILES_DF_COPY.ap+1

    results = []
    for i in range(repeats):
        defender_unit = Unit(*(DEFENDERS_DF[DEFENDERS_DF.unit_name==defender_name].values.flatten().tolist()))

        for attacker_name, weapon_profile_name in attacker_profile:
            attacker_weapon_profile = WeaponProfile(*(WEAPON_PROFILES_DF_COPY[(WEAPON_PROFILES_DF_COPY.weapon_name==weapon_profile_name) & (WEAPON_PROFILES_DF_COPY.unit_name==attacker_name)].values.flatten().tolist()))
            n_survivors = defender_unit.be_shot_at(attacker_weapon_profile)

            if defender_unit.n_models > 1:
                results.append(len(n_survivors))
            else:
                results.append(0 if not n_survivors else n_survivors[0])

    if defender_unit.n_models > 1:
        result = round(defender_unit.n_models - sum(results)/len(results), 2)
        success = '[x]' if math.ceil(result)>=defender_unit.n_models else '[ ]'
        message = f'\t{success} {weapon_profile_name} average kills: '.ljust(60)
        message += f'{result}/{defender_unit.n_models}'
        pprint_to_file(message)
        return round(result/defender_unit.n_models, 2), defender_unit.n_models
    else:
        result = round(defender_unit.w - sum(results)/len(results), 2)
        success = '[x]' if math.ceil(result)>=defender_unit.w else '[ ]'
        message = f'\t{success} {weapon_profile_name} average wounds:'.ljust(60)
        message += f'{result}/{defender_unit.w}'
        pprint_to_file(message)
        return round(result/defender_unit.w, 2), None



def simulate(attacker_name, repeats=100):
    global WEAPON_PROFILES_DF

    WEAPON_PROFILES_DF_COPY = WEAPON_PROFILES_DF[WEAPON_PROFILES_DF.unit_name==attacker_name].copy()

    pprint_to_file(f'calculating simulations n={repeats}\n')

    results = []

    total = 5 * len(DEFENDERS_DF.unit_name.values.tolist()) \
            * len(WEAPON_PROFILES_DF_COPY[WEAPON_PROFILES_DF_COPY.unit_name==attacker_name].weapon_name.values.tolist()) \
    
    with tqdm(total=total) as pbar:
        for defender_name in DEFENDERS_DF.unit_name.values.tolist():
            pprint_to_file('\n\n' + defender_name)
            for attacker_name in WEAPON_PROFILES_DF_COPY.unit_name.unique().tolist():
                pprint_to_file('\n  vs. ' + attacker_name)
                for weapon_profile_name in WEAPON_PROFILES_DF_COPY[WEAPON_PROFILES_DF_COPY.unit_name==attacker_name].weapon_name.values.tolist():
                    for buffs in [
                        [False, False, (False, False)],
                        [True, False, (False, False)],
                        [True, False, (True, False)],
                        [True, False, (True, True)],
                        [True, True, (True, True)]]:

                        args = [defender_name, [(attacker_name, weapon_profile_name)], *buffs, repeats]
                        score, unit_size = _simulate(*args)
                        defender_unit_key = defender_name
                        if unit_size: defender_unit_key += f'_{unit_size}'

                        guided = 'guided' if buffs[0] else 'no'
                        stealth_rerolls = 'stealth_rerolls' if buffs[1] else 'no'
                        strength = 'strength+1' if buffs[2][0] else 'no'
                        ap = 'ap+1' if buffs[2][1] else 'no'

                        results.append([attacker_name, defender_unit_key, weapon_profile_name, guided, strength, stealth_rerolls, ap, score])
                        pbar.update(1)

    pprint_to_file('\n\n\n')
    return results


def main():
    attacker_names = [
        # 'starscythe',
        # 'fireknife',
        # 'sunforge',
        # 'enforcer_fireknife',
        # 'coldstar_starscythe',
        # 'coldstar_sunforge,'
        # 'riptide',
        # 'broadside',
        # 'ghostkeel',
        'breacher_team'
    ]

    results = []
    for attacker_name in attacker_names:
        result = simulate(attacker_name)
        results.extend(result)
        pprint_to_file('\n\n\n\n\n')

    headers = ['attacker_name', 'defender_name', 'weapon_profile', 'guided', 'retaliation_cadre_strength', 'stealth_suit_rerolls', 'retaliation_cadre_ap', 'score']
    results_df = pd.DataFrame(results, columns=headers)
    results_df.to_csv('results.csv')

if __name__=="__main__":
    main()
