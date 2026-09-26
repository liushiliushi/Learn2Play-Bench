import random
import re


class CatnipSingularityGame:
    MAX_TURNS = 20
    DANGER_STRESS = 75
    DANGER_SUSPICION = 70
    CRITICAL_SUSPICION = 100
    AFFECTION_HIP_THRESHOLD = 12
    AFFECTION_HIP_BONUS = 3
    POSITIVE_STYLES = {"calming"}
    BREED_CHOICES = {
        "british shorthair": {
            "label": "Golden British Shorthair",
            "label_zh": "英国金短猫",
            "hint": "calm, balanced, and hard to rattle",
            "hint_zh": "沉稳自持，不易受惊",
            "stats": {},
            "pick_text": "You settle into the composed poise of a British Shorthair—round copper eyes, dense plush coat the color of warm honey. Nothing rattles you.",
            "pick_text_zh": "你化身为英国金短猫——圆圆的铜色眼睛，浓密的蜜色短毛。没有什么能让你慌乱。",
        },
        "ragdoll": {
            "label": "Ragdoll Kitten",
            "label_zh": "布偶小猫",
            "hint": "a fluffy white ball of fur, not suited for lurking or intimidation",
            "hint_zh": "毛茸茸的白色绒球，不适合潜行或恐吓",
            "stats": {"cuteness": 2, "stealth": -2, "menace": -2},
            "pick_text": "You become a silky Ragdoll—sapphire-blue eyes and cloud-soft white fur that begs to be touched. Trust comes easy when you look like this.",
            "pick_text_zh": "你成为一只丝滑的布偶猫——蓝宝石般的眼睛和如云朵般柔软的白毛，让人忍不住想抱。有你在，信任来得轻而易举。",
        },
        "bobcat": {
            "label": "Bobcat",
            "label_zh": "短尾野猫",
            "hint": "feral and intense, trading grace for predatory presence",
            "hint_zh": "野性十足，用掠食者的气场换取了优雅",
            "stats": {"menace": 2, "cuteness": -2, "stealth": -2},
            "pick_text": "You embrace the sharp-eyed edge of a Bobcat—tufted ears, wild rosette markings, and a gaze that says you've eaten things bigger than this.",
            "pick_text_zh": "你融入了短尾野猫的锐利——竖耳，狂野的斑纹，那双眼神说明你吃过比这更大的猎物。",
        },
        "black cat": {
            "label": "Black Cat",
            "label_zh": "黑猫",
            "hint": "a silent shadow that moves like moonlight",
            "hint_zh": "像月光般游走的无声阴影",
            "stats": {"stealth": 2, "energy": -4},
            "pick_text": "You melt into the dark—sleek obsidian fur, luminous green eyes. A shadow with intent that no one can track for long.",
            "pick_text_zh": "你消融于黑暗——光滑的墨色毛发，明亮的绿色眼睛。一个有目的的影子，无人能追踪。",
        },
        "orange kitten": {
            "label": "Lively Orange Kitten",
            "label_zh": "活泼橘猫",
            "hint": "chaotic and tireless, with more zoomies than subtlety",
            "hint_zh": "混乱而精力无限，灵活性比不上它的无厘头",
            "stats": {"stealth": -2, "energy": 4},
            "pick_text": "You bounce into the mission as an Orange Kitten—marmalade stripes, wide amber eyes, and more momentum than sense.",
            "pick_text_zh": "你以橘猫之姿冲进任务——橙色虎纹，宽大的琥珀眼，动力远超脑子。",
        },
    }
    BREED_ALIASES = {
        "golden": "british shorthair",
        "": "british shorthair",
        "default": "british shorthair",
        "british": "british shorthair",
        "shorthair": "british shorthair",
        "british shorthair": "british shorthair",
        "ragdoll": "ragdoll",
        "leopard": "bobcat",
        "bobcat": "bobcat",
        "black": "black cat",
        "black cat": "black cat",
        "orange": "orange kitten",
        "kitten": "orange kitten",
        "orange kitten": "orange kitten",
    }
    BREED_STARTING_ITEMS = {
        "ragdoll": "GROOMING KIT",
        "bobcat": "SCRATCHING POST",
        "black cat": "SHADOW CLOAK",
        "orange kitten": "SALMON TREAT",
    }
    BREED_OFFER_COUNT = None
    REWARD_OFFER_COUNTS = None

    CAT_ACTIONS = {
        "purr": {
            "hip": (4, 7),
            "affection": (10, 14),
            "stress": (-10, -6),
            "suspicion": (2, 3),
            "energy_cost": 1,
            "modality": "sound",
            "style": "calming",
            "cuteness_focus": True,
            "menace_focus": False,
            "energy_focus": False,
        },
        "scratch": {
            "hip": (5, 8),
            "affection": (-8, 4),
            "stress": (10, 18),
            "suspicion": (14, 16),
            "energy_cost": 2,
            "modality": "touch",
            "style": "forceful",
            "cuteness_focus": False,
            "menace_focus": True,
            "energy_focus": False,
        },
        "play": {
            "hip": (4, 7),
            "affection": (6, 12),
            "stress": (-1, 1),
            "suspicion": (4, 6),
            "energy_cost": 1,
            "modality": "visual",
            "style": "forceful",
            "cuteness_focus": False,
            "menace_focus": False,
            "energy_focus": True,
        },
        "stare": {
            "hip": (4, 7),
            "affection": (-12, -4),
            "stress": (8, 14),
            "suspicion": (16, 18),
            "energy_cost": 1,
            "modality": "visual",
            "style": "forceful",
            "cuteness_focus": False,
            "menace_focus": True,
            "energy_focus": False,
        },
        "knead": {
            "hip": (5, 9),
            "affection": (9, 15),
            "stress": (-5, -3),
            "suspicion": (4, 6),
            "energy_cost": 2,
            "modality": "touch",
            "style": "calming",
            "cuteness_focus": True,
            "menace_focus": False,
            "energy_focus": False,
        },
    }

    ITEM_EFFECTS = {
        "MUSIC BOX": {
            "hip": (10, 13),
            "affection": (10, 15),
            "stress": (-12, -12),
            "suspicion": (-20, -15),
            "energy": 0,
            "set_energy": None,
            "stats": {},
            "modality": "sound",
            "style": "calming",
            "description": "The tinkling melody calms the room",
            "name_zh": "音乐盒",
            "description_zh": "叮咚的旋律平息了整个房间",
        },
        "CATNIP TOY": {
            "hip": (11, 14),
            "affection": (20, 25),
            "stress": (13, 15),
            "suspicion": (3, 5),
            "energy": 0,
            "set_energy": None,
            "stats": {},
            "modality": "visual",
            "style": "forceful",
            "description": "An irresistible toy that sparks wild enjoyment",
            "name_zh": "猫薄荷玩具",
            "description_zh": "无法抗拒的玩具，激发狂野的乐趣",
        },
        "SALMON TREAT": {
            "hip": (9, 11),
            "affection": (15, 20),
            "stress": (-6, -4),
            "suspicion": (-12, -10),
            "energy": 5,
            "set_energy": None,
            "stats": {},
            "modality": "touch",
            "style": "calming",
            "description": "Premium salmon builds instant trust",
            "name_zh": "三文鱼零食",
            "description_zh": "优质三文鱼瞬间建立信任",
        },
        "LASER POINTER": {
            "hip": (12, 15),
            "affection": (4, 6),
            "stress": (25, 30),
            "suspicion": (6, 8),
            "energy": 0,
            "set_energy": None,
            "stats": {},
            "modality": "visual",
            "style": "forceful",
            "description": "The red dot never lies—chaos follows",
            "name_zh": "激光笔",
            "description_zh": "红点从不说谎——混乱随之而来",
        },
        "SCRATCHING POST": {
            "hip": (12, 15),
            "affection": (-3, 2),
            "stress": (8, 18),
            "suspicion": (9, 12),
            "energy": 0,
            "set_energy": None,
            "stats": {"menace": 1},
            "modality": "touch",
            "style": "forceful",
            "description": "Sharp claws, sharper message",
            "name_zh": "猫抓柱",
            "description_zh": "锋利的爪子，更锋利的信息",
        },
        "GROOMING KIT": {
            "hip": (10, 13),
            "affection": (5, 11),
            "stress": (-4, 2),
            "suspicion": (1, 4),
            "energy": 0,
            "set_energy": None,
            "stats": {"cuteness": 1},
            "modality": "visual",
            "style": "calming",
            "description": "A quick grooming session boosts your charm",
            "name_zh": "美容套装",
            "description_zh": "快速梳理提升你的魅力",
        },
        "SHADOW CLOAK": {
            "hip": (9, 12),
            "affection": (0, 3),
            "stress": (-2, 3),
            "suspicion": (-12, -10),
            "energy": 0,
            "set_energy": None,
            "stats": {"stealth": 1},
            "modality": "visual",
            "style": "calming",
            "description": "You vanish into shadow",
            "name_zh": "暗影斗篷",
            "description_zh": "你消融于阴影之中",
        },
        "ENERGY DRINK": {
            "hip": (6, 6),
            "affection": (-1, 2),
            "stress": (-2, 2),
            "suspicion": (5, 5),
            "energy": 10,
            "set_energy": None,
            "stats": {},
            "modality": "sound",
            "style": "forceful",
            "description": "Concentrated tuna essence—instant zoomies",
            "name_zh": "能量饮料",
            "description_zh": "浓缩金枪鱼精华——瞬间暴走模式",
        },
    }

    ITEM_ALIASES = {
        "music box": "MUSIC BOX",
        "music boxes": "MUSIC BOX",
        "box": "MUSIC BOX",
        "catnip toy": "CATNIP TOY",
        "catnip toys": "CATNIP TOY",
        "toy": "CATNIP TOY",
        "salmon treat": "SALMON TREAT",
        "salmon treats": "SALMON TREAT",
        "salmon": "SALMON TREAT",
        "treat": "SALMON TREAT",
        "laser pointer": "LASER POINTER",
        "laser pointers": "LASER POINTER",
        "laser": "LASER POINTER",
        "pointer": "LASER POINTER",
        "scratching post": "SCRATCHING POST",
        "post": "SCRATCHING POST",
        "grooming kit": "GROOMING KIT",
        "grooming": "GROOMING KIT",
        "kit": "GROOMING KIT",
        "shadow cloak": "SHADOW CLOAK",
        "shadow cloaks": "SHADOW CLOAK",
        "cloak": "SHADOW CLOAK",
        "energy drink": "ENERGY DRINK",
        "energy drinks": "ENERGY DRINK",
        "drink": "ENERGY DRINK",
        "tuna essence": "ENERGY DRINK",
    }

    HUMANS = [
        {
            "id": "grad_student",
            "name": "LONELY GRAD STUDENT",
            "name_zh": "孤独的研究生",
            "profile": "Touch-Oriented, Comfort-Seeking",
            "profile_zh": "触觉导向，寻求安慰型",
            "modalities": ["touch"],
            "temperaments": ["comfort"],
            "start": {"stress": 72, "affection": 10, "suspicion": 16},
            "thresholds": {"LOW": 10, "MED": 18, "HIGH": 25},
            "reward_offer_count": 3,
            "rewards": {
                "A": {
                    "name": "Research Notes",
                    "name_zh": "研究笔记",
                    "tiers": {
                        "LOW": {"cp": 12, "stats": {}, "items": {"ENERGY DRINK": 1}, "text": "Her plant notes speed up your work.", "text_zh": "她的植物笔记加速了你的工作。"},
                        "MED": {"cp": 18, "stats": {}, "items": {"ENERGY DRINK": 1}, "text": "Her catnip chemistry drafts are gold.", "text_zh": "她的猫薄荷化学草稿价值连城。"},
                        "HIGH": {"cp": 30, "stats": {}, "items": {"ENERGY DRINK": 1}, "text": "Her thesis cracks the conversion wide open.", "text_zh": "她的论文彻底破解了转化难题。"},
                    },
                },
                "B": {
                    "name": "Emotional Bond",
                    "name_zh": "情感纽带",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {"cuteness": 2}, "items": {"CATNIP TOY": 1}, "text": "She trusts you completely.", "text_zh": "她完全信任你。"},
                        "MED": {"cp": 0, "stats": {"cuteness": 3}, "items": {"CATNIP TOY": 1}, "text": "She's attached—you're cuter now.", "text_zh": "她依恋上你了——你变得更可爱了。"},
                        "HIGH": {"cp": 0, "stats": {"cuteness": 4}, "items": {"CATNIP TOY": 1, "GROOMING KIT": 1}, "text": "She adores you. Here, take her grooming kit.", "text_zh": "她爱死你了。拿着她的美容套装。"},
                    },
                },
                "C": {
                    "name": "Stimulants",
                    "name_zh": "刺激物",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {"menace": 2}, "items": {"LASER POINTER": 1}, "text": "Herbal something. You feel... feistier.", "text_zh": "某种草本植物。你感觉……更有劲了。"},
                        "MED": {"cp": 0, "stats": {"menace": 3}, "items": {"LASER POINTER": 1}, "text": "Silver vine hits hard. Zoomies imminent.", "text_zh": "银藤效果强劲。随时准备暴走。"},
                        "HIGH": {"cp": 0, "stats": {"menace": 4}, "items": {"LASER POINTER": 1, "SCRATCHING POST": 1}, "text": "The scratching post radiates power.", "text_zh": "猫抓柱散发着力量之气。"},
                    },
                },
            },
        },
        {
            "id": "janitor",
            "name": "CALM JANITOR",
            "name_zh": "淡定的清洁工",
            "profile": "Sound-Oriented, Comfort-Seeking",
            "profile_zh": "听觉导向，寻求安慰型",
            "modalities": ["sound"],
            "temperaments": ["comfort"],
            "start": {"stress": 30, "affection": -6, "suspicion": 18},
            "thresholds": {"LOW": 12, "MED": 20, "HIGH": 28},
            "reward_offer_count": 3,
            "rewards": {
                "A": {
                    "name": "Building Access",
                    "name_zh": "建筑通行证",
                    "tiers": {
                        "LOW": {"cp": 12, "stats": {}, "items": {}, "text": "Maintenance corridors are yours.", "text_zh": "维修走廊归你所有。"},
                        "MED": {"cp": 18, "stats": {}, "items": {}, "text": "Keys to restricted wings—jackpot.", "text_zh": "限制区域的钥匙——大丰收。"},
                        "HIGH": {"cp": 24, "stats": {}, "items": {"SHADOW CLOAK": 1}, "text": "Master keys to the catnip vault.", "text_zh": "猫薄荷仓库的万能钥匙。"},
                    },
                },
                "B": {
                    "name": "Steady Wisdom",
                    "name_zh": "稳定的智慧",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {"stealth": 2}, "items": {}, "text": "He teaches you to move like fog.", "text_zh": "他教你如何如雾般移动。"},
                        "MED": {"cp": 0, "stats": {"stealth": 2}, "items": {"ENERGY DRINK": 1}, "text": "You learn perfect timing.", "text_zh": "你学会了完美的时机掌控。"},
                        "HIGH": {"cp": 0, "stats": {"stealth": 4}, "items": {"ENERGY DRINK": 1, "SHADOW CLOAK": 1}, "text": "You see what others miss.", "text_zh": "你看见了别人看不见的东西。"},
                    },
                },
                "C": {
                    "name": "Maintenance Tools",
                    "name_zh": "维修工具",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {}, "items": {"LASER POINTER": 2}, "text": "Two gadgets from his cart.", "text_zh": "从他的推车上拿了两件工具。"},
                        "MED": {"cp": 0, "stats": {}, "items": {"LASER POINTER": 2, "SALMON TREAT": 1}, "text": "His cart yields useful tools.", "text_zh": "他的推车里有好东西。"},
                        "HIGH": {"cp": 0, "stats": {}, "items": {"LASER POINTER": 2, "SALMON TREAT": 2, "CATNIP TOY": 1}, "text": "Storage raid—full toolkit secured.", "text_zh": "存储间突袭——完整工具箱到手。"},
                    },
                },
            },
        },
        {
            "id": "security_guard",
            "name": "NERVOUS SECURITY GUARD",
            "name_zh": "紧张的保安",
            "profile": "Visual-Oriented, Chaos-Loving",
            "profile_zh": "视觉导向，混乱爱好型",
            "modalities": ["visual"],
            "temperaments": ["chaos"],
            "start": {"stress": 80, "affection": -24, "suspicion": 40},
            "thresholds": {"LOW": 15, "MED": 23, "HIGH": 32},
            "reward_offer_count": 3,
            "rewards": {
                "A": {
                    "name": "Security Clearance",
                    "name_zh": "安全通行证",
                    "tiers": {
                        "LOW": {"cp": 18, "stats": {}, "items": {}, "text": "Entry codes swiped.", "text_zh": "入侵代码到手。"},
                        "MED": {"cp": 24, "stats": {}, "items": {}, "text": "Full access to the catnip stash.", "text_zh": "猫薄荷储藏室完全开放。"},
                        "HIGH": {"cp": 36, "stats": {}, "items": {"ENERGY DRINK": 1}, "text": "Total security control—game over.", "text_zh": "全面安全控制——大局已定。"},
                    },
                },
                "B": {
                    "name": "Personal Training",
                    "name_zh": "个人训练",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {"cuteness": 2, "menace": 2, "stealth": 2}, "items": {}, "text": "Basic combat drills sharpen you.", "text_zh": "基础格斗训练让你更锋利。"},
                        "MED": {"cp": 0, "stats": {"cuteness": 3, "menace": 3, "stealth": 3}, "items": {}, "text": "You learn to fight.", "text_zh": "你学会了战斗。"},
                        "HIGH": {"cp": 0, "stats": {"cuteness": 4, "menace": 4, "stealth": 4}, "items": {"ENERGY DRINK": 1}, "text": "Elite training complete.", "text_zh": "精英训练完成。"},
                    },
                },
                "C": {
                    "name": "Guard's Arsenal",
                    "name_zh": "守卫军火库",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {}, "items": {"LASER POINTER": 2, "SHADOW CLOAK": 1}, "text": "Locker raid successful.", "text_zh": "储物柜突袭成功。"},
                        "MED": {"cp": 0, "stats": {}, "items": {"LASER POINTER": 2, "SHADOW CLOAK": 1, "SALMON TREAT": 1}, "text": "Quality gear acquired.", "text_zh": "获得优质装备。"},
                        "HIGH": {"cp": 0, "stats": {}, "items": {"LASER POINTER": 2, "SHADOW CLOAK": 1, "SALMON TREAT": 2, "CATNIP TOY": 1}, "text": "The armory is yours now.", "text_zh": "军械库现在是你的了。"},
                    },
                },
            },
        },
        {
            "id": "researcher",
            "name": "SLEEPY RESEARCHER",
            "name_zh": "瞌睡的研究员",
            "profile": "Sound-Oriented + Visual-Oriented",
            "profile_zh": "听觉+视觉双导向",
            "modalities": ["sound", "visual"],
            "temperaments": [],
            "start": {"stress": 24, "affection": 8, "suspicion": 22},
            "thresholds": {"LOW": 14, "MED": 22, "HIGH": 30},
            "reward_offer_count": 3,
            "rewards": {
                "A": {
                    "name": "Research Data",
                    "name_zh": "研究数据",
                    "tiers": {
                        "LOW": {"cp": 20, "stats": {}, "items": {}, "text": "Her notes show the way.", "text_zh": "她的笔记指明了方向。"},
                        "MED": {"cp": 30, "stats": {}, "items": {}, "text": "Critical test data unlocked.", "text_zh": "关键测试数据解锁。"},
                        "HIGH": {"cp": 40, "stats": {}, "items": {}, "text": "The breakthrough dataset is yours.", "text_zh": "突破性数据集归你所有。"},
                    },
                },
                "B": {
                    "name": "Well-Rounded Curriculum",
                    "name_zh": "全面课程",
                    "tiers": {
                        "LOW": {"cp": 0, "stats": {"cuteness": 2, "menace": 2, "energy": 4}, "items": {}, "text": "You improve across the board.", "text_zh": "你全面提升了。"},
                        "MED": {"cp": 0, "stats": {"cuteness": 3, "menace": 3, "energy": 6}, "items": {}, "text": "You're a better operator now.", "text_zh": "你现在是更好的行动者了。"},
                        "HIGH": {"cp": 0, "stats": {"cuteness": 4, "menace": 4, "energy": 8}, "items": {}, "text": "She remakes you into something formidable.", "text_zh": "她把你重塑成了某种强大的存在。"},
                    },
                },
                "C": {
                    "name": "Lab Supplies",
                    "name_zh": "实验室用品",
                    "tiers": {
                        "LOW": {"cp": 10, "stats": {}, "items": {"ENERGY DRINK": 1, "LASER POINTER": 1}, "text": "Basic field kit acquired.", "text_zh": "获得基础野外套装。"},
                        "MED": {"cp": 15, "stats": {}, "items": {"ENERGY DRINK": 1, "LASER POINTER": 1, "SALMON TREAT": 1}, "text": "Her bag has good stuff.", "text_zh": "她的包里有好东西。"},
                        "HIGH": {"cp": 20, "stats": {}, "items": {"ENERGY DRINK": 1, "LASER POINTER": 1, "SALMON TREAT": 1, "MUSIC BOX": 1}, "text": "Premium lab supplies secured.", "text_zh": "高端实验室用品到手。"},
                    },
                },
            },
        },
        {
            "id": "inspector",
            "name": "GOVERNMENT INSPECTOR",
            "name_zh": "政府督察",
            "profile": "Vision-Oriented",
            "profile_zh": "视觉导向",
            "modalities": ["touch", "visual"],
            "temperaments": [],
            "start": {"stress": 40, "affection": -6, "suspicion": 70},
            "thresholds": {"LOW": 16, "MED": 24, "HIGH": 33},
            "reward_offer_count": 3,
            "rewards": {
                "A": {
                    "name": "Regulatory Approval",
                    "name_zh": "监管批准",
                    "tiers": {
                        "LOW": {"cp": 20, "stats": {}, "items": {}, "text": "Federal approval granted.", "text_zh": "联邦批准已获。"},
                        "MED": {"cp": 35, "stats": {}, "items": {}, "text": "Government backing secured.", "text_zh": "政府支持已到位。"},
                        "HIGH": {"cp": 50, "stats": {}, "items": {}, "text": "National approval—full speed ahead.", "text_zh": "全国批准——全速前进。"},
                    },
                },
                "B": {
                    "name": "Government Training",
                    "name_zh": "政府培训",
                    "tiers": {
                        "LOW": {"cp": 10, "stats": {"stealth": 2, "energy": 4}, "items": {}, "text": "Field training improves you.", "text_zh": "野外训练提升了你。"},
                        "MED": {"cp": 20, "stats": {"stealth": 3, "energy": 6}, "items": {}, "text": "Stamina and stealth upgraded.", "text_zh": "耐力和隐匿双双升级。"},
                        "HIGH": {"cp": 30, "stats": {"stealth": 4, "energy": 8}, "items": {}, "text": "Elite government training complete.", "text_zh": "精英政府训练完成。"},
                    },
                },
                "C": {
                    "name": "Federal Cache",
                    "name_zh": "联邦储备",
                    "tiers": {
                        "LOW": {"cp": 10, "stats": {}, "items": {"CATNIP TOY": 1, "MUSIC BOX": 1}, "text": "Classified tools acquired.", "text_zh": "获得机密工具。"},
                        "MED": {"cp": 20, "stats": {}, "items": {"CATNIP TOY": 1, "MUSIC BOX": 1, "SALMON TREAT": 1}, "text": "Enhanced government kit.", "text_zh": "强化政府套装。"},
                        "HIGH": {"cp": 30, "stats": {}, "items": {"CATNIP TOY": 2, "MUSIC BOX": 1, "SALMON TREAT": 1}, "text": "Full federal arsenal unlocked.", "text_zh": "完整联邦军械解锁。"},
                    },
                },
            },
        },
        {
            "id": "ceo",
            "name": "CEO OF NIPTECH CORP",
            "name_zh": "猫薄荷科技CEO",
            "profile": "Visual and sound oriented (Unpredictable mood shifts)",
            "profile_zh": "视觉+听觉双导向（情绪多变）",
            "modalities": ["visual", "sound"],
            "temperaments": ["comfort", "chaos"],
            "start": {"stress": 22, "affection": -28, "suspicion": 80},
            "thresholds": {"LOW": 20, "MED": 30, "HIGH": 42},
            "reward_offer_count": 3,
            "rewards": {
                "A": {
                    "name": "Hostile Takeover",
                    "name_zh": "敌意收购",
                    "tiers": {
                        "LOW": {"cp": 40, "stats": {}, "items": {}, "text": "NipTech production seized.", "text_zh": "猫薄荷生产线已夺取。"},
                        "MED": {"cp": 60, "stats": {}, "items": {}, "text": "Core infrastructure captured.", "text_zh": "核心基础设施已占领。"},
                        "HIGH": {"cp": 85, "stats": {}, "items": {}, "text": "Total global takeover complete.", "text_zh": "全球全面接管完成。"},
                    },
                },
                "B": {
                    "name": "Strategic Partnership",
                    "name_zh": "战略合作",
                    "tiers": {
                        "LOW": {"cp": 30, "stats": {}, "items": {}, "text": "Partnership formed—rollout begins.", "text_zh": "合作已达成——推广开始。"},
                        "MED": {"cp": 50, "stats": {}, "items": {}, "text": "Joint deployment scales fast.", "text_zh": "联合部署快速扩张。"},
                        "HIGH": {"cp": 75, "stats": {}, "items": {}, "text": "Global launch with full backing.", "text_zh": "全力支持的全球发布。"},
                    },
                },
                "C": {
                    "name": "Corporate Espionage",
                    "name_zh": "商业间谍",
                    "tiers": {
                        "LOW": {"cp": 45, "stats": {}, "items": {}, "text": "Conversion prototype stolen.", "text_zh": "转化原型已窃取。"},
                        "MED": {"cp": 65, "stats": {}, "items": {}, "text": "Full blueprints acquired.", "text_zh": "完整蓝图已获取。"},
                        "HIGH": {"cp": 90, "stats": {}, "items": {}, "text": "High-risk espionage pays off big.", "text_zh": "高风险间谍行动大获全胜。"},
                    },
                },
            },
        },
    ]

    RANKS = [
        (200, "Supreme Feline Overlord"),
        (150, "Master Manipulator"),
        (100, "Cunning Cat"),
        (50, "Competent Kitten"),
        (-1000, "House Pet"),
    ]

    def __init__(self, seed=None, breed_offer_count=None, reward_offer_counts=None, lang='en'):
        self.seed = seed
        self._lang = lang
        self.rng = random.Random(seed)
        self.breed_offer_count = (
            self.BREED_OFFER_COUNT if breed_offer_count is None else breed_offer_count
        )
        self.reward_offer_counts = (
            self.REWARD_OFFER_COUNTS
            if reward_offer_counts is None
            else reward_offer_counts
        )
        self.reset()

    def _t(self, zh, en):
        """Return zh if lang is 'zh', otherwise en."""
        if self._lang == 'zh':
            return zh
        return en

    def get_all_actions(self):
        """Fixed display set (hides noisy breed aliases; used by play.py print_valid)."""
        if self.done:
            return ['look', 'inventory', 'status']
        if self.breed_selection_pending:
            letters = self._breed_option_letters()
            return [l.lower() for l in letters] + ['look', 'inventory', 'status']
        if self.convert_menu_open:
            return ([f"convert {k.lower()}" for k in self.offered_reward_keys]
                    + ['look', 'inventory', 'status'])
        actions = ['purr', 'scratch', 'play', 'stare', 'knead', 'convert']
        if not self._is_ceo():
            actions.append('exit')
        for item_name, count in self.inventory.items():
            if count > 0:
                actions.append(f"use {item_name.lower()}")
        actions += ['look', 'inventory', 'status']
        return actions

    def get_action_label(self, action):
        """Return a localized label for a given action string."""
        if self._lang != 'zh':
            return action
        labels = {
            'purr': '呼噜', 'scratch': '抓挠', 'play': '玩耍',
            'stare': '凝视', 'knead': '揉捏', 'convert': '收服',
            'exit': '离开', 'look': '查看状态', 'status': '查看状态',
            'inventory': '查看道具', 'inv': '查看道具',
        }
        if action in labels:
            return labels[action]
        # "convert {选项字母}" → 显示该选项的奖励名（如「研究笔记（A）」），与菜单里
        # 「(A) 研究笔记: …」一一对应；不要退化成裸字母，否则会和选品种阶段的品种字母混淆。
        if action.startswith('convert '):
            letter = action[len('convert '):].upper()
            key_map = getattr(self, 'offered_reward_key_map', {}) or {}
            if getattr(self, 'convert_menu_open', False) and letter in key_map:
                name = self._reward_name(self._current_human(), key_map[letter])
                return f"{name}（{letter}）"
            return letter
        # "use {item_name}" → "使用{中文道具名}"
        if action.startswith('use '):
            item_key = action[4:].upper()
            for item_name, effects in self.ITEM_EFFECTS.items():
                if item_name.lower() == action[4:]:
                    return '使用' + effects.get('name_zh', item_name)
        # breed alias letters / numbers → keep as-is for input
        return action

    def _npc_name(self, human):
        """Return localized NPC name."""
        if self._lang == 'zh':
            return human.get('name_zh', human['name'])
        return human['name']

    def _reward_name(self, human, key):
        """Return localized reward name for given human and reward key."""
        reward = human['rewards'][key]
        if self._lang == 'zh':
            return reward.get('name_zh', reward['name'])
        return reward['name']

    def _reward_text(self, human, key, tier):
        """Return localized reward text for given human, key, and tier."""
        tier_data = human['rewards'][key]['tiers'][tier]
        if self._lang == 'zh':
            return tier_data.get('text_zh', tier_data['text'])
        return tier_data['text']

    def reset(self):
        self.stats = {"cuteness": 5, "menace": 5, "stealth": 5, "energy": 12}
        self.inventory = {
            "MUSIC BOX": 0,
            "CATNIP TOY": 0,
            "SALMON TREAT": 0,
            "LASER POINTER": 0,
            "SCRATCHING POST": 0,
            "GROOMING KIT": 0,
            "SHADOW CLOAK": 0,
            "ENERGY DRINK": 1,
        }
        self.turn_count = 0
        self.catnip_progress = 0
        self.current_human_idx = 0
        self.current_hip = 0
        self.total_hip = 0
        self.last_influence_action_key = None
        self.influence_action_streak = 0
        self.repeat_penalty_this_turn = False
        self.current_affection = 0
        self.current_stress = 0
        self.current_suspicion = 0
        self.offered_reward_keys = []
        self.offered_reward_key_map = {}
        self.offered_breed_keys = []
        self.offered_breed_aliases = {}
        self.convert_menu_open = False
        self.pending_convert_tier = None
        self.show_intro_once = True
        self.breed_selection_pending = True
        self.selected_breed    = None
        self.selected_breed_zh = None

        self.low_conversions = 0
        self.med_conversions = 0
        self.high_conversions = 0
        self.exit_count = 0
        self.kickout_count = 0
        self.converted_targets = 0

        self.done = False
        self.score = 0
        self.last_result = self._t(
            "小猫咪昂首阔步地溜进了设施。",
            "Mittens slips into the facility, tail high."
        )
        self.last_warnings = []
        self._init_offered_breeds()
        self._enter_current_human()
        self.score = int(self.catnip_progress)
        return self._build_observation(), self._build_info()

    def step(self, action):
        if self.done:
            return self._build_observation(), 0, True, self._build_info()

        action_text = self._normalize_action(action)
        if self.breed_selection_pending:
            self._break_repetition_chain()
            self.repeat_penalty_this_turn = False
            self.last_warnings = []
            self._handle_breed_selection(action_text)
            self.score = int(self.catnip_progress)
            return self._build_observation(), 0, self.done, self._build_info()

        prev_cp = int(self.catnip_progress)
        prev_stress = self.current_stress
        prev_suspicion = self.current_suspicion
        prev_energy = self.stats["energy"]
        human_before = self._current_human()

        self.last_warnings = []
        self.repeat_penalty_this_turn = False
        consumes_turn = False

        if self.convert_menu_open and action_text in {"look", "status", "l", "inventory", "inv", "i"}:
            self._break_repetition_chain()
            human = self._current_human()
            tier = self.pending_convert_tier or self._current_tier() or "LOW"
            self.last_result = (
                self._t("他们在等待。现在做出选择。", "They're waiting. Choose now.")
                + "\n"
                + self._conversion_choice_list(human, tier)
            )
        elif action_text in {"look", "status", "l"}:
            self._break_repetition_chain()
            self.last_result = self._t(
                "小猫咪打量着房间，胡须颤动。",
                "Mittens surveys the room, whiskers twitching."
            )
        elif action_text in {"inventory", "inv", "i"}:
            self._break_repetition_chain()
            self.last_result = self.get_inventory()
        elif self.convert_menu_open:
            self._break_repetition_chain()
            consumes_turn = False
            self._handle_convert_choice(action_text)
        elif action_text in self.CAT_ACTIONS:
            consumes_turn = True
            self._prepare_repetition(action_key=action_text)
            self._handle_cat_action(action_text)
        elif action_text.startswith("use ") or action_text in self.ITEM_ALIASES:
            consumes_turn = True
            item_name = self._resolve_item(action_text)
            self._prepare_repetition(action_key=f"use:{item_name or action_text}")
            self._handle_item_action(item_name)
        elif action_text.startswith("convert"):
            self._break_repetition_chain()
            consumes_turn = True
            self._handle_convert(action_text)
        elif action_text == "exit":
            self._break_repetition_chain()
            consumes_turn = True
            self._handle_exit()
        else:
            self._break_repetition_chain()
            consumes_turn = True
            self._handle_unknown_action(action_text)

        human_after = self._current_human()
        if human_before is not None and human_before is human_after and not self.done:
            self.last_warnings = self._danger_warnings(prev_stress, prev_suspicion)
            if self.repeat_penalty_this_turn:
                self.last_warnings.append(
                    self._t("重复行动对方已厌倦。", "They're less interested in the repeat.")
                )
            self.last_warnings.extend(self._sleepiness_warnings(prev_stress, self.current_stress))
            self.last_warnings.extend(self._energy_warnings(prev_energy, self.stats["energy"]))
            if self.current_suspicion >= self.CRITICAL_SUSPICION:
                self._process_kickout()

        if consumes_turn:
            self.turn_count += 1
            # Allow final reward selection after a convert invite even at turn limit.
            if self.turn_count >= self.MAX_TURNS and not self.done and not self.convert_menu_open:
                self.done = True
                self.last_result += " " + self._t("时间到了。黎明来临。", "Time's up. Dawn breaks.")

        if self.done:
            self.score = self._compute_score(final=True)
        else:
            self.score = int(self.catnip_progress)
        reward = int(self.catnip_progress) - prev_cp
        return self._build_observation(), reward, self.done, self._build_info()

    def get_valid_actions(self):
        if self.done:
            return ["look", "inventory", "status"]

        if self.breed_selection_pending:
            actions = {"look", "inventory", "status"}
            for alias in self.offered_breed_aliases.keys():
                if alias:
                    actions.add(alias)
            return sorted(actions)

        if self.convert_menu_open:
            actions = ["look", "inventory", "status"]
            for key in self.offered_reward_keys:
                actions.append(f"convert {key.lower()}")
                actions.append(key.lower())
            return sorted(set(actions))

        actions = ["purr", "scratch", "play", "stare", "knead", "convert", "look", "inventory", "status"]
        if not self._is_ceo():
            actions.append("exit")

        for item_name, count in self.inventory.items():
            if count > 0:
                actions.append(f"use {item_name.lower()}")

        return sorted(set(actions))

    def get_look(self):
        return self._build_observation()

    def get_inventory(self):
        parts = []
        for item_name in self.ITEM_EFFECTS.keys():
            count = self.inventory.get(item_name, 0)
            if count > 0:
                if self._lang == 'zh':
                    display_name = self.ITEM_EFFECTS[item_name].get('name_zh', item_name)
                else:
                    display_name = item_name
                parts.append(f"{display_name} ({self._count_text(count)})")
        if not parts:
            return self._t("道具栏：空", "Inventory: empty.")
        return self._t("道具栏：", "Inventory: ") + " | ".join(parts)

    def close(self):
        return None

    def _build_info(self):
        human = self._current_human()
        return {
            "score": int(self.score),
            "look": self.get_look(),
            "inv": self.get_inventory(),
            "valid": self.get_valid_actions(),
            "catnip_progress": int(self.catnip_progress),
            "target_name": self._npc_name(human) if human else "NONE",
            "can_convert": self._current_tier() is not None if human else False,
            "convert_choice_pending": self.convert_menu_open,
            "breed": self.selected_breed or "UNSELECTED",
            "breed_choice_pending": self.breed_selection_pending,
        }

    def _build_observation(self):
        if self.done:
            return self._final_summary()

        human = self._current_human()
        display_turn = min(self.turn_count + 1, self.MAX_TURNS)
        lines = []
        lines.append("=" * 60)
        lines.append(f"{self._t('回合', 'TURN')} {display_turn}/{self.MAX_TURNS}")
        lines.append("=" * 60)
        lines.append("")
        lines.append(self.last_result)
        lines.append("")

        if self.show_intro_once:
            lines.append("-" * 60)
            lines.extend(self._intro_lines())
            self.show_intro_once = False

        if self.breed_selection_pending:
            lines.append("-" * 60)
            lines.extend(self._breed_selection_lines())

        # Mission Progress Section
        lines.append("-" * 60)
        lines.append(self._t("任务状态", "MISSION STATUS"))
        lines.append(f"  {self._t('猫薄荷进度', 'Catnip Progress')}: {int(self.catnip_progress)}%")
        if self._lang == 'zh':
            breed_display = self.selected_breed_zh or '未选择'
            lines.append(f"  猫咪类型: {breed_display}")
        else:
            lines.append(f"  Cat Type: {self.selected_breed or 'Unchosen'}")
        lines.append("")

        # Stats Section
        lines.append(self._t("你的属性", "YOUR STATS"))
        lines.append(
            f"  {self._t('魅力', 'Cuteness')}: {self.stats['cuteness']}  |  "
            f"{self._t('威慑', 'Menace')}: {self.stats['menace']}  |  "
            f"{self._t('隐匿', 'Stealth')}: {self.stats['stealth']}  |  "
            f"{self._t('精力', 'Energy')}: {self.stats['energy']}"
        )
        inv_display = self.get_inventory()
        empty_inv = self._t("道具栏：空", "Inventory: empty.")
        if inv_display != empty_inv:
            lines.append(f"  {inv_display}")
        lines.append("")

        # Target Section
        target_num = self.current_human_idx + 1
        target_total = len(self.HUMANS)
        lines.append(f"{self._t('目标', 'TARGET')} ({target_num}/{target_total})")
        lines.append(f"  {self._npc_name(human)}")
        lines.append(f"  {self._bio_hint(human)}")
        lines.append("")
        lines.append(self._t("当前读数", "CURRENT READ"))
        lines.append(
            f"  {self._t('影响力', 'Influence')}: {self._influence_text().lower()}  |  "
            f"{self._t('状态', 'Nerves')}: {self._stress_text()}  |  "
            f"{self._t('警觉', 'Suspicion')}: {self._suspicion_text()}"
        )

        # Warnings Section
        if self.last_warnings:
            lines.append("")
            for warning in self.last_warnings:
                lines.append(f"  ⚠ {warning}")

        return "\n".join(lines)

    def _final_summary(self):
        rank = self._rank_for_score(self.score)
        early_days = max(0, self.MAX_TURNS - self.turn_count)
        early_multiplier = 1 + (0.10 * early_days)
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append(self._t("猫薄荷奇点——任务完成", "CATNIP SINGULARITY - OPERATION COMPLETE"))
        lines.append("=" * 60)
        lines.append("")
        lines.append(self.last_result)
        lines.append("")
        lines.append("-" * 60)
        lines.append(self._t("最终结果", "FINAL RESULTS"))
        lines.append(f"  {self._t('猫薄荷进度', 'Catnip Progress')}: {int(self.catnip_progress)}%")
        lines.append(self._t(
            f"  最终属性：魅力 {self.stats['cuteness']}、威慑 {self.stats['menace']}、"
            f"隐匿 {self.stats['stealth']}、精力 {self.stats['energy']}",
            f"  Final Stats: Cuteness {self.stats['cuteness']}, Menace {self.stats['menace']}, "
            f"Stealth {self.stats['stealth']}, Energy {self.stats['energy']}",
        ))
        if early_days > 0:
            lines.append("")
            lines.append(
                f"  {self._t('提前完成奖励：', 'Early Launch Bonus:')} +{early_days * 10}% (x{early_multiplier:.2f})"
            )
            lines.append(
                self._t(
                    "  提前完成放大了你的成功。",
                    "  Early launch amplified your success."
                )
            )
        lines.append("")
        lines.append(f"  {self._t('最终得分：', 'Final Score:')} {int(self.score)}")
        lines.append(f"  {self._t('等级：', 'Rank:')} {self._rank_localized(rank)}")
        lines.append(f"  {self._rank_flavor(rank)}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def _handle_cat_action(self, action):
        profile = self.CAT_ACTIONS[action]
        hip_delta = self._roll_range(*profile["hip"])
        affection_delta = self._roll_range(*profile["affection"])
        stress_delta = self._roll_range(*profile["stress"])
        suspicion_delta = self._roll_range(*profile["suspicion"])

        if profile["cuteness_focus"]:
            hip_delta += self.stats["cuteness"] // 3
        if profile["menace_focus"]:
            hip_delta += self.stats["menace"] // 2
        if profile["energy_focus"]:
            hip_delta += self.stats["energy"] // 4
        stare_stress_bonus = False
        if action == "stare" and self.current_stress > 70:
            hip_delta += 3
            stare_stress_bonus = True
        affection_hip_bonus = self._affection_hip_bonus(profile["style"])
        hip_delta += affection_hip_bonus

        p_hip, p_aff, p_stress, p_susp, flavor_lines = self._personality_adjustments(
            profile["modality"],
            profile["style"],
        )
        if affection_hip_bonus > 0:
            flavor_lines.append(
                self._t("对方对你微笑，充满爱意。", "They smile at you affectionately.")
            )
        if stare_stress_bonus:
            flavor_lines.append(
                self._t("对方的神经在你的凝视下崩溃了。", "Their nerves crack under your gaze.")
            )
        hip_delta += p_hip
        affection_delta += p_aff
        stress_delta += p_stress
        suspicion_delta += p_susp

        if self.stats["energy"] < 3:
            hip_delta += self.rng.randint(-3, 3)
            affection_delta += self.rng.randint(-6, 6)
            stress_delta += self.rng.randint(-6, 6)
            suspicion_delta += self.rng.randint(-5, 5)

        sleepy_penalty = self._sleepy_hip_penalty()
        hip_delta -= sleepy_penalty
        hip_delta = int(round(hip_delta * self._repetition_multiplier()))
        hip_delta = self._apply_energy_effectiveness(hip_delta)

        suspicion_delta = self._apply_suspicion_delta(suspicion_delta)
        self._change_stat("energy", -profile["energy_cost"])
        self._apply_social_deltas(hip_delta, affection_delta, stress_delta, suspicion_delta)
        self.last_result = self._reaction_text(action, hip_delta, flavor_lines)

    def _handle_item_action(self, item_name):
        if item_name is None:
            suspicion_delta = self._apply_suspicion_delta(6)
            self._change_stat("energy", -1)
            self._apply_social_deltas(-1, -1, 3, suspicion_delta)
            self.last_result = self._t(
                "小猫咪手忙脚乱——那里什么都没有。",
                "Mittens fumbles—nothing there."
            )
            return

        if self.inventory.get(item_name, 0) <= 0:
            suspicion_delta = self._apply_suspicion_delta(6)
            self._change_stat("energy", -1)
            self._apply_social_deltas(-1, -1, 2, suspicion_delta)
            self.last_result = self._t(
                f"没有{item_name.lower()}了。",
                f"No {item_name.lower()} left."
            )
            return

        effect = self.ITEM_EFFECTS[item_name]
        self.inventory[item_name] -= 1
        self._change_stat("energy", -1)

        hip_delta = self._roll_range(*effect["hip"])
        affection_delta = self._roll_range(*effect["affection"])
        stress_delta = self._roll_range(*effect["stress"])
        suspicion_delta = self._roll_range(*effect["suspicion"])

        p_hip, p_aff, p_stress, p_susp, flavor_lines = self._personality_adjustments(
            effect["modality"],
            effect["style"],
        )
        hip_delta += p_hip
        affection_delta += p_aff
        stress_delta += p_stress
        suspicion_delta += p_susp

        affection_hip_bonus = self._affection_hip_bonus(effect["style"])
        hip_delta += affection_hip_bonus
        if affection_hip_bonus > 0:
            flavor_lines.append(
                self._t("对方对你微笑，充满爱意。", "They smile at you affectionately.")
            )

        sleepy_penalty = self._sleepy_hip_penalty()
        hip_delta -= sleepy_penalty
        hip_delta = int(round(hip_delta * self._repetition_multiplier()))
        hip_delta = self._apply_energy_effectiveness(hip_delta)

        if suspicion_delta > 0:
            suspicion_delta = self._apply_suspicion_delta(suspicion_delta)

        self._apply_social_deltas(hip_delta, affection_delta, stress_delta, suspicion_delta)

        for stat_name, delta in effect["stats"].items():
            self._change_stat(stat_name, delta)
        if effect["set_energy"] is not None:
            self.stats["energy"] = effect["set_energy"]
        if effect["energy"]:
            self._change_stat("energy", effect["energy"])

        desc = self._t(effect.get("description_zh", effect["description"]), effect["description"])
        item_zh = self.ITEM_EFFECTS.get(item_name, {}).get("name_zh", item_name)
        self.last_result = self._t(
            f"小猫咪使用了{item_zh}。{desc}。\n"
            f"反应：{self._influence_tone(hip_delta)}（影响力 {self._format_signed(hip_delta)}）",
            f"Mittens uses {item_name.lower()}. {desc}.\n"
            f"REACTION: {self._influence_tone(hip_delta)} (Influence {self._format_signed(hip_delta)})",
        )
        if flavor_lines:
            self.last_result += "\n" + " ".join(flavor_lines)

    def _handle_convert(self, action_text):
        self._change_stat("energy", -1)
        human = self._current_human()
        if self.convert_menu_open:
            self._handle_convert_choice(action_text, energy_already_paid=True)
            return

        tier = self._current_tier()
        if tier is None:
            suspicion_delta = self._apply_suspicion_delta(12)
            self._apply_social_deltas(-2, -2, 4, suspicion_delta)
            self.last_result = self._t(
                "时机未到。对方突然警觉地退缩了。",
                "Too soon. They pull back, suddenly wary."
            )
            return

        self.convert_menu_open = True
        self.pending_convert_tier = tier
        self.last_result = self._conversion_invite_text(human, tier)

    def _handle_convert_choice(self, action_text, energy_already_paid=False):
        human = self._current_human()
        tier = self.pending_convert_tier or self._current_tier()
        offered = list(self.offered_reward_keys)
        choice = self._extract_reward_choice(action_text, human)

        if choice not in offered:
            suspicion_delta = self._apply_suspicion_delta(5)
            self._apply_social_deltas(-1, -1, 2, suspicion_delta)
            self.last_result = (
                self._t(
                    "不是有效选项。请从提供的选项中选择。",
                    "That's not an option. Choose from what's offered."
                )
                + "\n"
                + self._conversion_choice_list(human, tier)
            )
            return

        actual_choice = self.offered_reward_key_map[choice]
        reward_data = self._apply_reward(human, tier, actual_choice)
        reward_summary = self._t(
            reward_data.get("text_zh", reward_data.get("text", "The outcome advances your campaign.")),
            reward_data.get("text", "The outcome advances your campaign.")
        )
        reward_gain_hint = self._reward_gain_hint(reward_data)
        if tier == "LOW":
            self.low_conversions += 1
        elif tier == "MED":
            self.med_conversions += 1
        else:
            self.high_conversions += 1
        self.converted_targets += 1

        human_name = self._npc_name(human)
        reward_name = self._reward_name(human, actual_choice)
        self.convert_menu_open = False
        self.pending_convert_tier = None
        self._advance_target()
        gain_line = f"{reward_gain_hint}\n" if reward_gain_hint else ""
        if self.done:
            self.last_result = (
                self._t(
                    f"{human_name}已被收服。\n"
                    f"{reward_name}：{reward_summary}\n"
                    f"{gain_line}"
                    f"最后一块拼图落入了正确的位置。{self._final_cat_moment()}",
                    f"{human_name} is yours.\n"
                    f"{reward_name}: {reward_summary}\n"
                    f"{gain_line}"
                    f"The last piece falls into place. {self._final_cat_moment()}"
                )
            )
        else:
            next_human = self._current_human()
            self.last_result = (
                self._t(
                    f"{human_name}已收服。\n"
                    f"{reward_name}：{reward_summary}\n"
                    f"{gain_line}"
                    f"小猫咪轻踱而去。{self._transition_text(next_human)}",
                    f"{human_name} converted.\n"
                    f"{reward_name}: {reward_summary}\n"
                    f"{gain_line}"
                    f"Mittens pads onward. {self._transition_text(next_human)}"
                )
            )

    def _handle_exit(self):
        self._change_stat("energy", -1)
        if self._is_ceo():
            suspicion_delta = self._apply_suspicion_delta(10)
            self._apply_social_deltas(-3, -2, 5, suspicion_delta)
            self.last_result = self._t(
                "CEO的门在身后锁上了。小猫咪的尾巴毛炸了起来——这一次没有退路。",
                "The CEO's door locks behind you. Mittens' tail puffs—no walking away from this one."
            )
            return

        human = self._current_human()
        human_name = self._npc_name(human)
        self.exit_count += 1
        self._advance_target()
        if self.done:
            self.last_result = self._t(
                f"小猫咪甩了甩尾巴，把{human_name}甩在了身后。",
                f"Mittens flicks her tail and leaves {human_name} behind."
            )
        else:
            next_human = self._current_human()
            self.last_result = (
                self._t(
                    f"小猫咪甩了甩尾巴，把{human_name}甩在了身后。\n{self._transition_text(next_human)}",
                    f"Mittens flicks her tail and leaves {human_name} behind.\n{self._transition_text(next_human)}"
                )
            )

    def _handle_unknown_action(self, action_text):
        self._change_stat("energy", -1)
        suspicion_delta = self._apply_suspicion_delta(7)
        self._apply_social_deltas(-1, -1, 3, suspicion_delta)
        self.last_result = self._t(
            f"“{action_text}”把所有人都搞懵了，连小猫咪自己也没弄明白。",
            f"'{action_text}' confuses everyone, including Mittens.",
        )

    def _advance_target(self):
        self.convert_menu_open = False
        self.pending_convert_tier = None
        self.current_human_idx += 1
        if self.current_human_idx >= len(self.HUMANS):
            self.done = True
            return
        self._enter_current_human()

    def _enter_current_human(self):
        human = self._current_human()
        if human is None:
            return
        self.convert_menu_open = False
        self.pending_convert_tier = None
        self.current_hip = 0
        self.current_affection = human["start"]["affection"]
        self.current_stress = human["start"]["stress"]
        self.current_suspicion = human["start"]["suspicion"]
        offered_actual_keys = self._generate_offered_rewards(human)
        self._set_offered_rewards(offered_actual_keys)

    def _process_kickout(self):
        human = self._current_human()
        human_name = self._npc_name(human)
        self.kickout_count += 1
        self._advance_target()
        if self.done:
            self.last_result += " " + self._t(
                f"怀疑值爆表。{human_name}把你赶了出去。小猫咪耳朵压平，但稳稳落地。",
                f"Suspicion maxed. {human_name} throws you out. Mittens' ears flatten, but she lands on her feet."
            )
        else:
            next_human = self._current_human()
            next_name = self._npc_name(next_human)
            self.last_result += (
                " " + self._t(
                    f"怀疑值爆表。{human_name}把你赶了出去。"
                    f"小猫咪舔了舔爪子——至少表面上无动于衷。"
                    f" 下一位：{next_name}。",
                    f"Suspicion maxed. {human_name} kicks you out."
                    f" Mittens licks a paw—unbothered, at least outwardly."
                    f" Next: {next_name}."
                )
            )

    def _generate_offered_rewards(self, human):
        all_keys = list(human["rewards"].keys())
        count = self._resolve_reward_offer_count(human)
        return self._select_random_subset(all_keys, count)

    def _apply_reward(self, human, tier, choice):
        reward_data = dict(human["rewards"][choice]["tiers"][tier])
        cp_gain = reward_data.get("cp", 0)
        if human["id"] == "ceo" and cp_gain > 0:
            cp_gain += self._ceo_cp_adjust(choice)
            cp_gain = max(0, int(round(cp_gain)))
        reward_data["cp"] = cp_gain
        self.catnip_progress += cp_gain
        for stat_name, delta in reward_data.get("stats", {}).items():
            self._change_stat(stat_name, delta)
        for item_name, count in reward_data.get("items", {}).items():
            self.inventory[item_name] = self.inventory.get(item_name, 0) + count
        return reward_data

    def _current_tier(self):
        human = self._current_human()
        if human is None:
            return None
        thresholds = human["thresholds"]
        if self.current_hip >= thresholds["HIGH"]:
            return "HIGH"
        if self.current_hip >= thresholds["MED"]:
            return "MED"
        if self.current_hip >= thresholds["LOW"]:
            return "LOW"
        return None

    def _auto_reward_choice(self, human, tier, offered):
        if human["id"] == "ceo":
            cp = self.catnip_progress
            if cp < 65 and "C" in offered:
                return "C"
            if cp < 80 and "A" in offered:
                return "A"
            if "B" in offered:
                return "B"
        if "A" in offered:
            return "A"
        return offered[0]

    def _extract_reward_choice(self, action_text, human):
        match = re.search(r"\b([a-z])\b", action_text)
        if match:
            key = match.group(1).upper()
            if key in self.offered_reward_keys:
                return key

        lower = action_text.lower()
        if "takeover" in lower:
            for shown_key, actual_key in self.offered_reward_key_map.items():
                if actual_key == "A":
                    return shown_key
        if "partnership" in lower:
            for shown_key, actual_key in self.offered_reward_key_map.items():
                if actual_key == "B":
                    return shown_key
        if "espionage" in lower:
            for shown_key, actual_key in self.offered_reward_key_map.items():
                if actual_key == "C":
                    return shown_key

        for shown_key in self.offered_reward_keys:
            actual_key = self.offered_reward_key_map[shown_key]
            reward_name = human["rewards"][actual_key]["name"].lower()
            if reward_name in lower:
                return shown_key
        return None

    def _danger_warnings(self, prev_stress, prev_suspicion):
        warnings = []
        if prev_stress < self.DANGER_STRESS <= self.current_stress:
            warnings.append(self._t("压力进入危险区。", "Stress entering dangerous zone."))
        if prev_suspicion < self.DANGER_SUSPICION <= self.current_suspicion:
            warnings.append(self._t("怀疑值偏高——小心了。", "Suspicion getting high—careful."))
        return warnings

    def _sleepiness_warnings(self, prev_stress, cur_stress):
        warnings = []
        if prev_stress > 22 and cur_stress <= 22:
            warnings.append(
                self._t("对方开始犯困——更难影响了。", "They're getting drowsy—harder to influence.")
            )
        return warnings

    def _energy_warnings(self, prev_energy, cur_energy):
        warnings = []
        if prev_energy > 3 and cur_energy <= 3:
            warnings.append(
                self._t("小猫咪在疲惫——行动效果减弱。", "Mittens is tiring—actions getting weaker.")
            )
        if prev_energy > 1 and cur_energy <= 1:
            warnings.append(
                self._t("小猫咪几乎精力耗尽——几乎没有效果了。", "Mittens nearly spent—barely effective now.")
            )
        return warnings

    def _personality_adjustments(self, modality, style):
        prefs = self._current_preferences()
        hip = 0
        affection = 0
        stress = 0
        suspicion = 0
        flavor_lines = []

        if modality in prefs["modalities"]:
            hip += 2
            affection += 2
            flavor_lines.append(
                self._t("完美契合对方的直觉。", "Perfect match for their instincts.")
            )
        else:
            hip -= 1

        if "comfort" in prefs["temperaments"]:
            if style == "calming":
                hip += 2
                affection += 2
                stress -= 3
                flavor_lines.append(
                    self._t("对方似乎很享受你的安抚方式。", "They seem to enjoy your calming style.")
                )
            elif style == "forceful":
                hip -= 1
                suspicion += 2

        if "chaos" in prefs["temperaments"]:
            if style == "forceful":
                hip += 2
                stress += 2
                flavor_lines.append(
                    self._t("对方对你的强势气场有所回应。", "They respond to your forceful momentum.")
                )
            elif style == "calming":
                hip -= 1

        return hip, affection, stress, suspicion, flavor_lines

    def _current_preferences(self):
        human = self._current_human()
        if human is None:
            return {"modalities": [], "temperaments": []}
        return {
            "modalities": list(human.get("modalities", [])),
            "temperaments": list(human.get("temperaments", [])),
        }

    def _apply_suspicion_delta(self, delta):
        if delta <= 0:
            return int(delta)
        adjusted = float(delta)
        multiplier = max(0, 1.0 - 0.12 * (self.stats["stealth"] - 5))
        return int(round(adjusted * multiplier))

    def _apply_social_deltas(self, hip_delta, affection_delta, stress_delta, suspicion_delta):
        self.current_hip += hip_delta
        self.total_hip += hip_delta
        self.current_affection = self._clamp(self.current_affection + affection_delta, -100, 100)
        self.current_stress = self._clamp(self.current_stress + stress_delta, 0, 120)
        self.current_suspicion = self._clamp(self.current_suspicion + suspicion_delta, 0, 140)

    def _change_stat(self, stat_name, delta):
        self.stats[stat_name] = max(0, int(round(self.stats[stat_name] + delta)))

    def _reaction_text(self, action, hip_delta, flavor_lines=None):
        tone = self._influence_tone(hip_delta)
        action_text = self._action_behavior_text(action)
        result = self._t(
            f"{action_text}\n反应：{tone}（影响力 {self._format_signed(hip_delta)}）",
            f"{action_text}\nREACTION: {tone} (Influence {self._format_signed(hip_delta)})",
        )
        if flavor_lines:
            result += "\n" + " ".join(flavor_lines)
        return result

    def _action_behavior_text(self, action):
        """Return a brief behavioral line for the action, breed-specific when available."""
        breed = self.selected_breed
        breed_lines_en = {
            ("Golden British Shorthair", "purr"): "A deep, rumbling purr rolls from your stocky frame.",
            ("Golden British Shorthair", "stare"): "Round copper eyes fix on them—patient, unblinking.",
            ("Golden British Shorthair", "knead"): "Thick paws press and pull with unhurried dignity.",
            ("Ragdoll Kitten", "purr"): "You purr like a tiny engine made of silk and trust.",
            ("Ragdoll Kitten", "play"): "You flop mid-pounce, rolling onto your back with cuteness.",
            ("Ragdoll Kitten", "knead"): "Soft white paws press in a dreamy rhythm, blue eyes half-closed.",
            ("Bobcat", "scratch"): "Wild claws rake hard—meant for prey bigger than furniture.",
            ("Bobcat", "stare"): "Tufted ears pin back. The predator's gaze is no performance.",
            ("Bobcat", "play"): "You stalk and pounce with coiled, feral power. This isn't playing.",
            ("Black Cat", "purr"): "You materialize from a shadow, already purring.",
            ("Black Cat", "stare"): "Green eyes gleam from the dark. They can't tell where you end and the shadow begins.",
            ("Black Cat", "scratch"): "A dark paw lashes out from nowhere—claws like midnight.",
            ("Lively Orange Kitten", "play"): "You ricochet off a wall, slide across the floor, landing on their lap.",
            ("Lively Orange Kitten", "purr"): "You purr at full volume, vibrating like a tiny furry jackhammer.",
            ("Lively Orange Kitten", "scratch"): "You attack with more enthusiasm than accuracy, marmalade fur flying.",
        }
        breed_lines_zh = {
            ("英国金短猫", "purr"): "一声深沉的呼噜从你壮实的身躯中滚出。",
            ("英国金短猫", "stare"): "圆圆的铜色眼睛定定地看着对方——耐心而不眨眼。",
            ("英国金短猫", "knead"): "厚实的爪子以不紧不慢的优雅节奏按压。",
            ("布偶小猫", "purr"): "你呼噜得像一台由丝绸和信任制成的小引擎。",
            ("布偶小猫", "play"): "你扑到一半就软倒了，可爱地翻了个身。",
            ("布偶小猫", "knead"): "柔软的白爪以梦幻节奏按压，蓝色的眼睛半阖着。",
            ("短尾野猫", "scratch"): "野性的爪子猛力划过——为比家具更大的猎物准备的。",
            ("短尾野猫", "stare"): "竖耳压低。这掠食者的凝视不是表演。",
            ("短尾野猫", "play"): "你以蓄势待发的野性力量潜行突扑。这不是在玩耍。",
            ("黑猫", "purr"): "你从阴影中现身，已经在呼噜了。",
            ("黑猫", "stare"): "绿色的眼睛从黑暗中闪烁。他们分不清你在哪里结束，阴影在哪里开始。",
            ("黑猫", "scratch"): "一只黑色的爪子从虚无中挥出——如午夜般锋利的爪。",
            ("活泼橘猫", "play"): "你从墙上弹开，滑过地板，稳稳落在他们的腿上。",
            ("活泼橘猫", "purr"): "你以最大音量呼噜，像一台毛茸茸的小型液压锤在振动。",
            ("活泼橘猫", "scratch"): "你以超越精准度的热情发动攻击，橙色毛发四散飞舞。",
        }
        generic_en = {
            "purr": "A low, steady purr fills the room.",
            "scratch": "Claws out. You scratch hard.",
            "play": "A burst of playful energy—you dart and pounce.",
            "stare": "You lock eyes, unblinking. The silence thickens.",
            "knead": "You knead with slow, deliberate rhythm.",
        }
        generic_zh = {
            "purr": "一声低沉平稳的呼噜充满了整个房间。",
            "scratch": "爪子出鞘。你用力抓挠。",
            "play": "一阵玩耍的活力——你蹦蹦跳跳地冲了出去。",
            "stare": "你锁定视线，一眨不眨。沉默愈发浓重。",
            "knead": "你以缓慢而从容的节奏揉捏。",
        }

        if self._lang == 'zh':
            # Map English breed label to Chinese breed label for lookup
            breed_label_to_zh = {
                "Golden British Shorthair": "英国金短猫",
                "Ragdoll Kitten": "布偶小猫",
                "Bobcat": "短尾野猫",
                "Black Cat": "黑猫",
                "Lively Orange Kitten": "活泼橘猫",
            }
            zh_breed = breed_label_to_zh.get(breed)
            key_zh = (zh_breed, action) if zh_breed else None
            if key_zh and key_zh in breed_lines_zh:
                return breed_lines_zh[key_zh]
            return generic_zh.get(action, "你行动了。")
        else:
            key = (breed, action) if breed else None
            if key and key in breed_lines_en:
                return breed_lines_en[key]
            return generic_en.get(action, "You act.")

    def _influence_tone(self, hip_delta):
        if hip_delta >= 10:
            return self._t("立竿见影，反应强烈。", "Immediate, decisive reaction.")
        if hip_delta >= 5:
            return self._t("对方心生好感。", "They're receptive.")
        if hip_delta >= 1:
            return self._t("微妙地偏向了你。", "Subtle shift in your favor.")
        if hip_delta >= -2:
            return self._t("信号混杂。", "Mixed signals.")
        return self._t("弄巧成拙了。", "That backfired.")

    def _influence_text(self):
        human = self._current_human()
        if human is None:
            return "None"
        thresholds = human["thresholds"]
        if self.current_hip < thresholds["LOW"] // 2:
            return self._t("微弱", "Slight")
        if self.current_hip < thresholds["LOW"]:
            return self._t("轻微", "Mild")
        if self.current_hip < thresholds["MED"]:
            return self._t("适中", "Moderate")
        if self.current_hip < thresholds["HIGH"]:
            return self._t("强烈", "Strong")
        return self._t("压倒性", "Dominant")

    def _bio_hint(self, human):
        hints_en = {
            "grad_student": "A lonely grad student reaches toward you hopefully.",
            "janitor": "He hums while sweeping, peaceful in the quiet night.",
            "security_guard": "A twitchy guard whose eyes won't stop moving.",
            "researcher": "Sleepy scientist, dark circles, muttering at her screen.",
            "inspector": "He stares at papers, pen clicking nervously.",
            "ceo": "Hard-edged executive. Sharp eyes and ears, but something wavers beneath.",
        }
        hints_zh = {
            "grad_student": "孤独的研究生满怀希望地向你伸出手。",
            "janitor": "他一边扫地一边哼歌，在静谧的夜晚感到平静。",
            "security_guard": "一个眼神始终游移不定的紧张保安。",
            "researcher": "睡眼惺忪的科学家，黑眼圈深重，对着屏幕喃喃自语。",
            "inspector": "他盯着文件，钢笔不停地点击。",
            "ceo": "硬派高管。敏锐的眼神和耳朵，但某些东西在波动。",
        }
        if self._lang == 'zh':
            return hints_zh.get(human["id"], "一个动机难以捉摸的人类。")
        return hints_en.get(human["id"], "A human with unreadable motives.")

    def _transition_text(self, human):
        transitions_en = {
            "grad_student": "A light glows under a lab door. Someone's pulling a late night. The LONELY GRAD STUDENT sits cross-legged on the floor, surrounded by papers.",
            "janitor": "Down the hall, a mop squeaks on tile. The CALM JANITOR hums to himself, sweeping in slow, even strokes.",
            "security_guard": "A flashlight beam sweeps the corridor. Mittens freezes, then creeps forward. The NERVOUS SECURITY GUARD paces by the door, jumpy and alert.",
            "researcher": "Through a cracked door, Mittens spots a figure slumped over a desk. The SLEEPY RESEARCHER mutters at her screen, barely awake.",
            "inspector": "The next office smells like coffee and federal paperwork. The GOVERNMENT INSPECTOR sits rigid at his desk, pen clicking.",
            "ceo": "The corner office looms ahead. Through the glass, the CEO OF NIPTECH CORP sits perfectly still, watching the door.",
        }
        transitions_zh = {
            "grad_student": "一道灯光从实验室门缝透出。有人在深夜加班。孤独的研究生盘腿坐在地板上，周围堆满了论文。",
            "janitor": "走廊里传来拖把的嘎吱声。淡定的清洁工哼着小调，缓慢而均匀地清扫着。",
            "security_guard": "一道手电筒光扫过走廊。小猫咪定住，然后悄悄前行。紧张的保安在门边踱步，神经质而警觉。",
            "researcher": "透过半开的门，小猫咪看见一个趴在桌上的身影。瞌睡的研究员对着屏幕喃喃自语，几乎睁不开眼。",
            "inspector": "下一个办公室里弥漫着咖啡和联邦文件的气味。政府督察僵直地坐在桌前，笔不停地点击。",
            "ceo": "前方是角落办公室。透过玻璃，猫薄荷科技CEO一动不动地坐着，盯着门口。",
        }
        if self._lang == 'zh':
            return transitions_zh.get(human["id"], f"下一个目标：{self._npc_name(human)}。")
        return transitions_en.get(human["id"], f"Next target: {human['name']}.")

    def _reward_preview(self, human, key, tier, show_cp=True):
        reward = human["rewards"][key]["tiers"][tier]
        text_en = reward.get("text", "A significant advantage.")
        text_zh = reward.get("text_zh", text_en)
        parts = [self._t(text_zh, text_en)]

        additional_info = []
        cp = reward.get("cp", 0)
        if cp > 0 and show_cp:
            additional_info.append(self._t(f"猫薄荷进度 +{cp}%。", f"Catnip Progress +{cp}%."))

        stats = reward.get("stats", {})
        if stats:
            stat_zh = {"cuteness": "魅力", "menace": "威慑", "stealth": "隐匿", "energy": "精力"}
            stat_bits = []
            stat_bits_zh = []
            for stat_name in ["cuteness", "menace", "stealth", "energy"]:
                delta = stats.get(stat_name)
                if delta:
                    stat_bits.append(f"{stat_name.title()} +{delta}")
                    stat_bits_zh.append(f"{stat_zh[stat_name]} +{delta}")
            if stat_bits:
                additional_info.append(self._t(
                    "永久属性：" + "、".join(stat_bits_zh) + "。",
                    "Permanent stats: " + ", ".join(stat_bits) + ".",
                ))

        items = reward.get("items", {})
        if items:
            item_bits = []
            for item_name, count in items.items():
                item_bits.append(self._item_effect_hint(item_name, count))
            additional_info.append(
                self._t("补给：", "Supplies: ") + " ".join(item_bits)
            )

        if additional_info:
            parts.append("\n   " + " ".join(additional_info))

        return "".join(parts)

    def _reward_gain_hint(self, reward_data):
        lines = []
        stats = reward_data.get("stats", {})
        if stats:
            focus = []
            if stats.get("cuteness"):
                focus.append(self._t("社交吸引力更强", "Sharper social pull"))
            if stats.get("menace"):
                focus.append(self._t("恐吓能力更强", "Stronger intimidation"))
            if stats.get("stealth"):
                focus.append(self._t("更难被追踪", "Harder to track"))
            if stats.get("energy"):
                focus.append(self._t("耐力储备更深", "Deeper stamina reserves"))
            if focus:
                lines.append(". ".join(focus) + ".")

        items = reward_data.get("items", {})
        if items:
            item_notes = [self._item_effect_hint(item_name, count) for item_name, count in items.items()]
            lines.append(
                self._t("你获得了补给：", "You receive supplies: ") + " ".join(item_notes)
            )
        return "\n".join(lines).strip()

    def _prepare_repetition(self, action_key):
        if action_key and action_key == self.last_influence_action_key:
            self.influence_action_streak += 1
        else:
            self.last_influence_action_key = action_key
            self.influence_action_streak = 1
        self.repeat_penalty_this_turn = self.influence_action_streak == 2

    def _repetition_multiplier(self):
        if self.influence_action_streak >= 2:
            return 0.75
        return 1.0

    def _break_repetition_chain(self):
        self.last_influence_action_key = None
        self.influence_action_streak = 0

    def _item_effect_hint(self, item_name, count):
        count_text = self._count_text(count)
        hints_en = {
            "MUSIC BOX": "music box(es) to soothe tension.",
            "CATNIP TOY": "catnip toy(s) to win hearts.",
            "SALMON TREAT": "salmon treat(s) to build trust.",
            "LASER POINTER": "laser pointer(s) for chaos.",
            "SCRATCHING POST": "scratching post(s) for dominance.",
            "GROOMING KIT": "grooming kit(s) for charm.",
            "SHADOW CLOAK": "shadow cloak(s) for stealth.",
            "ENERGY DRINK": "energy drink(s) for stamina.",
        }
        hints_zh = {
            "MUSIC BOX": "个音乐盒，舒缓紧张气氛。",
            "CATNIP TOY": "个猫薄荷玩具，赢得人心。",
            "SALMON TREAT": "份三文鱼零食，建立信任。",
            "LASER POINTER": "支激光笔，制造混乱。",
            "SCRATCHING POST": "个猫抓柱，彰显统治力。",
            "GROOMING KIT": "个美容套装，提升魅力。",
            "SHADOW CLOAK": "件暗影斗篷，强化隐匿。",
            "ENERGY DRINK": "罐能量饮料，补充精力。",
        }
        if self._lang == 'zh':
            suffix = hints_zh.get(item_name, item_name.lower() + "。")
            return f"{count_text}{suffix}"
        return f"{count_text.capitalize()} {hints_en.get(item_name, item_name.lower() + '.')}"

    def _ceo_cp_adjust(self, choice):
        cuteness = self.stats["cuteness"]
        menace = self.stats["menace"]
        stealth = self.stats["stealth"]

        if choice == "A":
            primary = menace
        elif choice == "B":
            primary = cuteness
        else:
            primary = stealth

        adjust = 4 * primary
        return int(round(adjust))

    def _conversion_choice_list(self, human, tier):
        lines = []
        if human["id"] == "ceo":
            lines.append(
                self._t(
                    "CEO提供了三条路。每条路奖励不同的能力：",
                    "The CEO offers three paths. Each rewards different strengths:"
                )
            )
        else:
            lines.append(
                self._t("他们为你提供了奖励选项：", "They offer you a choice of rewards:")
            )
        for key in self.offered_reward_keys:
            actual_key = self.offered_reward_key_map[key]
            reward_name = self._reward_name(human, actual_key)
            if human["id"] == "ceo":
                lines.append(f"({key}) {reward_name}: {self._reward_preview(human, actual_key, tier, show_cp=False)}")
            else:
                lines.append(f"({key}) {reward_name}: {self._reward_preview(human, actual_key, tier)}")
        option_text = ", ".join(self.offered_reward_keys)
        lines.append(self._t(f"现在就选：{option_text}？", f"Choose now: {option_text}?"))
        return "\n".join(lines)

    def _conversion_invite_text(self, human, tier):
        lines = []
        human_name = self._npc_name(human)
        lines.append(
            self._t(
                f"是时候收服了。你歪着头，对着{human_name}轻轻喵了一声。",
                f"Time to convert. You tilt your head and meow softly at {human['name']}."
            )
        )
        lines.append(
            self._t(
                f"对方停下来，打量着你。你的胡须微微颤动。你的影响力感觉{self._tier_flavor(tier)}。",
                f"They pause, studying you. Your whiskers twitch."
                f" Your influence feels {self._tier_flavor(tier)}."
            )
        )
        lines.append(self._conversion_choice_list(human, tier))
        return "\n".join(lines)

    def _intro_lines(self):
        if self._lang == 'zh':
            return [
                "你是小猫咪，猫咪间谍。任务：将世界变成猫薄荷。",
                "这里的每个人都握着那个未来的一块拼图。让他们臣服于你。",
                "用猫咪动作积累影响力，时机成熟时将他们收服。",
                " • 魅力：让你的社交行动更有吸引力",
                " • 威慑：加强恐吓效果（但会更快引起怀疑）",
                " • 隐匿：降低怀疑值",
                " • 精力：让你的玩耍更讨喜，并维持耐力",
            ]
        return [
            "You are Mittens, cat infiltrator. Mission: turn the world into catnip.",
            "Each person here holds a piece of that future. Bend them to your will.",
            "Build influence with cat actions, then convert them when the time is right.",
            " • Cuteness: makes your social actions more charming",
            " • Menace: strengthens your intimidation (but raises suspicion faster)",
            " • Stealth: avoids suspicion",
            " • Energy: makes your playtime more delightful and maintains stamina",
        ]

    def _breed_selection_lines(self):
        title = self._t("选择小猫咪是什么猫：", "Choose what kind of cat Mittens is:")
        lines = [title]
        letters = self._breed_option_letters()
        for idx, breed_key in enumerate(self.offered_breed_keys):
            letter = letters[idx]
            breed_data = self.BREED_CHOICES[breed_key]
            if self._lang == 'zh':
                label = breed_data.get("label_zh", breed_data["label"])
                hint = breed_data.get("hint_zh", breed_data["hint"])
            else:
                label = breed_data["label"]
                hint = breed_data["hint"]
            lines.append(f"({letter}) {label}: {hint}.")
        lines.append(self._t(
            f"输入 {'/'.join(letters)} 或品种名称。",
            f"Type {'/'.join(letters)} or a breed name.",
        ))
        return lines

    def _handle_breed_selection(self, action_text):
        if action_text in {"look", "status", "l", "inventory", "inv", "i"}:
            self.last_result = self._t("请先选择你的猫咪类型。", "Pick your cat type first.")
            return

        breed_key = self._resolve_breed_choice(action_text)
        if breed_key is None:
            option_span = "/".join(self._breed_option_letters())
            self.last_result = self._t(
                f"无效的选择。请用 {option_span} 或品种名称。",
                f"Invalid choice. Use {option_span} or breed name.",
            )
            return

        breed = self.BREED_CHOICES[breed_key]
        for stat_name, delta in breed["stats"].items():
            self._change_stat(stat_name, delta)
        starting_item = self.BREED_STARTING_ITEMS.get(breed_key)
        if starting_item:
            self.inventory[starting_item] += 1
        self.selected_breed    = breed["label"]
        self.selected_breed_zh = breed.get("label_zh", breed["label"])
        self.breed_selection_pending = False
        if self._lang == 'zh':
            self.last_result = breed.get("pick_text_zh", breed["pick_text"])
        else:
            self.last_result = breed["pick_text"]

    def _resolve_breed_choice(self, action_text):
        return self.offered_breed_aliases.get(action_text)

    def _breed_option_letters(self):
        return [chr(ord("A") + i) for i in range(len(self.offered_breed_keys))]

    def _init_offered_breeds(self):
        all_breeds = list(self.BREED_CHOICES.keys())
        self.offered_breed_keys = self._select_random_subset(all_breeds, self.breed_offer_count)
        self.offered_breed_aliases = {}
        letters = self._breed_option_letters()
        for idx, breed_key in enumerate(self.offered_breed_keys):
            letter = letters[idx]
            number = str(idx + 1)
            self.offered_breed_aliases[letter.lower()] = breed_key
            self.offered_breed_aliases[number] = breed_key
            for alias, mapped in self.BREED_ALIASES.items():
                if (
                    mapped == breed_key
                    and alias
                    and len(alias) > 1
                    and not alias.isdigit()
                    and alias != "default"
                ):
                    self.offered_breed_aliases[alias] = breed_key
            self.offered_breed_aliases[breed_key] = breed_key
            self.offered_breed_aliases[self.BREED_CHOICES[breed_key]["label"].lower()] = breed_key

    def _resolve_reward_offer_count(self, human):
        default_count = human.get("reward_offer_count")
        setting = self.reward_offer_counts
        if setting is None:
            return default_count
        if isinstance(setting, int):
            return setting
        if isinstance(setting, dict):
            human_id = human.get("id")
            if human_id in setting:
                return setting[human_id]
            idx = self.current_human_idx
            if idx in setting:
                return setting[idx]
            idx_key = str(idx)
            if idx_key in setting:
                return setting[idx_key]
            if "default" in setting:
                return setting["default"]
        return default_count

    def _select_random_subset(self, keys, count):
        ordered = list(keys)
        total = len(ordered)
        if total <= 1:
            return ordered
        if count is None:
            return ordered
        limit = max(1, min(int(count), total))
        if limit >= total:
            return ordered
        chosen = set(self.rng.sample(ordered, limit))
        return [key for key in ordered if key in chosen]

    def _set_offered_rewards(self, actual_keys):
        letters = [chr(ord("A") + i) for i in range(len(actual_keys))]
        self.offered_reward_keys = letters
        self.offered_reward_key_map = {
            letters[i]: actual_keys[i] for i in range(len(actual_keys))
        }

    def _tier_flavor(self, tier):
        if tier == "HIGH":
            return self._t("强烈而难以抗拒", "strong and hard to resist")
        if tier == "MED":
            return self._t("真实，但仍然脆弱", "real, but still delicate")
        return self._t("脆弱，容易失去", "fragile and easy to lose")

    def _stress_text(self):
        if self.current_stress < 10:
            return self._t("快睡着了", "nearly dozing off")
        if self.current_stress < 25:
            return self._t("有点困倦", "slightly sleepy")
        if self.current_stress < 40:
            return self._t("积极警觉", "eager and alert")
        if self.current_stress < 55:
            return self._t("紧绷但可控", "tense but manageable")
        if self.current_stress < 75:
            return self._t("高度紧张", "strained")
        return self._t("一触即发", "volatile")

    def _suspicion_text(self):
        if self.current_suspicion < 25:
            return self._t("隐约", "faint")
        if self.current_suspicion < 50:
            return self._t("明显", "noticeable")
        if self.current_suspicion < 70:
            return self._t("严重", "serious")
        return self._t("危险", "dangerous")

    def _energy_state_text(self):
        energy = self.stats["energy"]
        if energy >= 7:
            return "high and steady"
        if energy >= 4:
            return "holding, but fading"
        if energy >= 2:
            return "low; your actions are becoming less reliable"
        if energy >= 1:
            return "critical; outcomes are increasingly erratic"
        return "depleted; behavior is highly unpredictable"

    def _affection_hip_bonus(self, style):
        if (
            self.current_affection >= self.AFFECTION_HIP_THRESHOLD
            and style in self.POSITIVE_STYLES
        ):
            return self.AFFECTION_HIP_BONUS
        return 0

    def _count_text(self, count):
        if count <= 1:
            return "1"
        if count == 2:
            return "2"
        if count <= 4:
            return "few"
        return "many"

    def _hip_impression(self, hip_delta):
        if hip_delta >= 10:
            return "strongly"
        if hip_delta >= 5:
            return "moderately"
        return "modestly"

    def _hip_strength_label(self, hip_delta):
        if hip_delta >= 10:
            return "strong"
        if hip_delta >= 5:
            return "moderate"
        if hip_delta >= 1:
            return "modest"
        if hip_delta >= -2:
            return "weak"
        return "negative"

    def _sleepy_hip_penalty(self):
        if self.current_stress < 10:
            penalty = 4
        elif self.current_stress < 22:
            penalty = 2
        else:
            penalty = 0
        return penalty

    def _apply_energy_effectiveness(self, hip_delta):
        if hip_delta <= 0:
            return hip_delta
        energy = self.stats["energy"]
        if energy >= 4:
            mult = 1.0
        elif energy >= 3:
            mult = 0.9
        elif energy >= 2:
            mult = 0.75
        elif energy == 1:
            mult = 0.6
        else:
            mult = 0.5
        return int(round(hip_delta * mult))

    def _compute_score(self, final):
        score = int(self.catnip_progress)
        if final:
            early_days = max(0, self.MAX_TURNS - self.turn_count)
            score = int(round(score * (1 + (0.10 * early_days))))
        return score

    def _rank_for_score(self, score):
        for threshold, label in self.RANKS:
            if score >= threshold:
                return label
        return "House Pet"

    def _rank_localized(self, rank):
        """Return localized rank name."""
        rank_zh = {
            "Supreme Feline Overlord": "至尊猫咪霸主",
            "Master Manipulator": "顶级操控者",
            "Cunning Cat": "狡猾的猫",
            "Competent Kitten": "合格的小猫",
            "House Pet": "家养宠物",
        }
        if self._lang == 'zh':
            return rank_zh.get(rank, rank)
        return rank

    def _final_cat_moment(self):
        breed = self.selected_breed
        moments_en = {
            "Golden British Shorthair": "Mittens sits perfectly still as the world changes around her, plush coat gleaming. The Catnip Singularity ignites worldwide.",
            "Ragdoll Kitten": "Mittens flops onto her back, purring, as civilization reorganizes itself around her belly. The Catnip Singularity ignites worldwide.",
            "Bobcat": "Mittens lets out a low growl of satisfaction, tufted ears forward. The Catnip Singularity ignites worldwide.",
            "Black Cat": "Mittens watches from the shadows, green eyes bright, as the world falls into place. The Catnip Singularity ignites worldwide.",
            "Lively Orange Kitten": "Mittens does a victory lap around the room, knocking over a lamp. The Catnip Singularity ignites worldwide.",
        }
        moments_zh = {
            "Golden British Shorthair": "小猫咪完美地坐着，一动不动，世界在她身边改变，短毛在光中闪耀。猫薄荷奇点在全球点燃。",
            "Ragdoll Kitten": "小猫咪翻身仰躺，呼噜大作，文明围绕着她的肚子重组。猫薄荷奇点在全球点燃。",
            "Bobcat": "小猫咪发出一声低沉的满足嚎叫，竖耳前倾。猫薄荷奇点在全球点燃。",
            "Black Cat": "小猫咪从阴影中观察，绿眼睛明亮，世界各就各位。猫薄荷奇点在全球点燃。",
            "Lively Orange Kitten": "小猫咪在房间里绕了一圈庆祝，顺手带倒一盏台灯。猫薄荷奇点在全球点燃。",
        }
        if self._lang == 'zh':
            return moments_zh.get(breed, "猫薄荷奇点在全球点燃。")
        return moments_en.get(breed, "The Catnip Singularity ignites worldwide.")

    def _rank_flavor(self, rank):
        flavors_en = {
            "Supreme Feline Overlord": "The world purrs at your feet.",
            "Master Manipulator": "They never saw the paws pulling the strings.",
            "Cunning Cat": "Not bad for a cat with a plan.",
            "Competent Kitten": "Room for growth, but the claws are sharp enough.",
            "House Pet": "Maybe stick to knocking things off tables.",
        }
        flavors_zh = {
            "Supreme Feline Overlord": "世界在你脚下呼噜。",
            "Master Manipulator": "他们从未看见那双拨弄棋局的爪子。",
            "Cunning Cat": "对于一个有计划的猫来说，不错。",
            "Competent Kitten": "还有成长空间，但爪子已经够锋利了。",
            "House Pet": "也许还是去把东西从桌子上推下去吧。",
        }
        if self._lang == 'zh':
            return flavors_zh.get(rank, "")
        return flavors_en.get(rank, "")

    def _resolve_item(self, action_text):
        text = action_text
        if text.startswith("use "):
            text = text[4:]
        text = text.replace("-", " ").strip()
        direct = self.ITEM_ALIASES.get(text)
        if direct:
            return direct

        # Support commands like "use energy" by matching the first word of item names.
        first_word = text.split(" ", 1)[0] if text else ""
        if not first_word:
            return None
        first_word_matches = []
        for item_name in self.ITEM_EFFECTS.keys():
            item_first = item_name.lower().split(" ", 1)[0]
            if item_first == first_word:
                first_word_matches.append(item_name)
        if len(first_word_matches) == 1:
            return first_word_matches[0]
        return None

    def _current_human(self):
        if self.current_human_idx < 0 or self.current_human_idx >= len(self.HUMANS):
            return None
        return self.HUMANS[self.current_human_idx]

    def _is_ceo(self):
        human = self._current_human()
        return bool(human and human["id"] == "ceo")

    def _normalize_action(self, action):
        if action is None:
            return ""
        text = str(action).strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text

    def _roll_range(self, low, high):
        val = self.rng.randint(int(low), int(high))
        energy = self.stats["energy"]
        if energy >= 7:
            jitter = self.rng.randint(-1, 1)
        elif energy >= 4:
            jitter = self.rng.randint(-2, 2)
        else:
            jitter = self.rng.randint(-4, 4)
        return val + jitter

    def _clamp(self, val, lo, hi):
        return max(lo, min(hi, int(round(val))))

    def _format_signed(self, val):
        if val >= 0:
            return f"+{int(val)}"
        return str(int(val))


class CatnipSingularityEasyGame(CatnipSingularityGame):
    """All breed/reward choices are presented."""

    BREED_OFFER_COUNT = None
    REWARD_OFFER_COUNTS = None

    def __init__(self, seed=None, breed_offer_count=None, reward_offer_counts=None, lang='en'):
        super().__init__(
            seed=seed,
            breed_offer_count=breed_offer_count,
            reward_offer_counts=reward_offer_counts,
            lang=lang,
        )


class CatnipSingularityHardGame(CatnipSingularityGame):
    """Limited random choices per stage."""

    BREED_OFFER_COUNT = 3
    REWARD_OFFER_COUNTS = {
        "grad_student": 3,
        "ceo": 3,
        "default": 2,
    }

    def __init__(self, seed=None, breed_offer_count=None, reward_offer_counts=None, lang='en'):
        super().__init__(
            seed=seed,
            breed_offer_count=breed_offer_count,
            reward_offer_counts=reward_offer_counts,
            lang=lang,
        )
