{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "version": "2.0.0",
  "source": "UNIQA Retail Segmentation (Oct-Nov 2025, n=4004 representative survey) + UNIQA persona profiles (May 2026) + UNIQA funnel analysis (Dec 2025 - Feb 2026)",
  "last_updated": "2026-05-28",
  "language": "en",
  "notes": [
    "Three personas correspond to the three online-funnel-relevant market segments (out of six total UNIQA segments).",
    "All quantitative values sourced directly from UNIQA segmentation booklet (n=620 S1, n=688 S2, n=546 S3).",
    "Qualitative profiles and quotes come from UNIQA-provided persona sheets (May 2026).",
    "Teams may extend with sub-variants — declare extensions clearly."
  ],
  "shared_context": {
    "market_total_persons_18_75": 6500000,
    "online_funnel_traffic_share": {
      "segment_1": 0.3,
      "segment_2": 0.5,
      "segment_3": 0.2,
      "source": "UNIQA internal estimate, May 2026"
    },
    "current_online_conversion_baseline": {
      "rate": 0.056,
      "drop_offs": [
        {
          "step": "initial_price_display",
          "rate": 0.66
        },
        {
          "step": "additional_coverage_selection",
          "rate": 0.24
        },
        {
          "step": "final_price_after_health_questions",
          "rate": 0.78
        }
      ],
      "data_period": "2025-12-10 to 2026-02-01"
    },
    "traffic_source_mix": {
      "paid_and_organic_search_pct": 80,
      "active_hours_share_9_to_20_pct": 70
    }
  },
  "personas": {
    "segment_1": {
      "id": "segment_1",
      "name_short": "Rising Hybrids",
      "name_full": "Die aufsteigenden Hybriden",
      "sample_size": 620,
      "persona_archetype": {
        "name": "Judith Berger",
        "age": 43,
        "location": "Vienna, urban",
        "life_phase": "Established career, often family with children",
        "occupation": "Mid-to-upper management employee",
        "typical_quote": "I prefer to research things myself online — but for important decisions I want someone I can trust."
      },
      "market_size_persons": 975000,
      "market_share_pct": 15,
      "demographics": {
        "age_mean": 43.2,
        "age_distribution_pct": {
          "18_29": 26,
          "30_39": 21,
          "40_49": 16,
          "50_59": 17,
          "60_75": 20
        },
        "female_pct": 54,
        "male_pct": 46,
        "income_monthly_eur": 4042,
        "income_label": "above_average",
        "education": {
          "with_matura_pct": 45,
          "without_matura_pct": 55,
          "matura_significantly_above_average": true
        },
        "urbanity": {
          "city_pct": 38,
          "intermediate_pct": 11,
          "countryside_pct": 51
        },
        "regional_distribution_pct": {
          "vienna": 26,
          "lower_austria": 22,
          "upper_austria": 16,
          "styria": 12,
          "tyrol": 10,
          "salzburg": 5,
          "carinthia": 5,
          "vorarlberg": 3,
          "burgenland": 2
        },
        "household": {
          "single_pct": 24,
          "two_person_pct": 37,
          "three_person_pct": 17,
          "four_person_pct": 15,
          "five_plus_pct": 6,
          "in_partnership_pct": 66,
          "single_divorced_widowed_pct": 34,
          "with_children_pct": 31
        },
        "housing": {
          "apartment_pct": 55,
          "house_pct": 45,
          "ownership_pct": 51,
          "rent_pct": 48,
          "owned_apartment_pct": 16,
          "owned_house_pct": 35
        },
        "employment": {
          "employee_pct": 61,
          "retired_pct": 17
        },
        "transport_primary_pct": {
          "car": 52,
          "public_transport": 25
        },
        "vehicle_ownership_pct": {
          "car_combustion": 74,
          "bicycle": 40,
          "e_bicycle": 13,
          "motorcycle": 9,
          "e_car": 4
        }
      },
      "financial_assets_pct": {
        "life_insurance_pension": 50,
        "securities": 43,
        "building_savings": 39,
        "gold_precious_metals": 27,
        "real_estate": 20,
        "valuables": 17,
        "crypto": 12,
        "additional_real_estate": 11
      },
      "insurance_behavior": {
        "current_products_owned": 5.2,
        "new_purchase_intent_3y_products": 1.5,
        "kv_ownership_pct": 34,
        "kv_purchase_intent_3y_pct": 18,
        "switch_willingness_pct": 7,
        "general_attitude_positive_pct": 59,
        "monthly_insurance_spend_eur": 230.6,
        "net_promoter_score": 17,
        "uniqa_customer_pct": 35,
        "uniqa_main_insured_pct": 23,
        "advisor_type_pct": {
          "employed_insurance_advisor": 51,
          "independent_broker": 20,
          "general_agent": 9,
          "no_advisor": 12
        },
        "top_3_main_insurers_pct": {
          "uniqa": 23,
          "generali": 12,
          "allianz": 11
        },
        "current_holdings_pct": {
          "household": 86,
          "vehicle_liability": 71,
          "legal_protection": 55,
          "vehicle_comprehensive": 46,
          "accident": 45,
          "life_pension": 43,
          "home_ownership": 41,
          "health": 34,
          "death": 25,
          "travel": 20,
          "motorcycle_moped": 13,
          "occupational_disability": 12,
          "electronics": 12,
          "pet": 9,
          "bicycle_scooter": 4,
          "cyber": 2,
          "care": 1
        },
        "new_purchase_likelihood_3y_pct": {
          "household": 8,
          "vehicle_liability": 9,
          "legal_protection": 13,
          "vehicle_comprehensive": 9,
          "accident": 9,
          "life_pension": 11,
          "home_ownership": 4,
          "health": 18,
          "death": 12,
          "travel": 14,
          "motorcycle_moped": 3,
          "occupational_disability": 10,
          "electronics": 7,
          "pet": 8,
          "bicycle_scooter": 2,
          "cyber": 4,
          "care": 9
        }
      },
      "decision_drivers_pct": {
        "price_performance_ratio": 87,
        "tailored_products": 83,
        "personal_advisor_trust": 76,
        "compares_multiple_offers": 75,
        "values_apps_and_portals": 73,
        "low_engagement_only_what_needed": 60,
        "broad_life_coverage": 56,
        "single_insurer_preference": 55,
        "advised_at_life_events": 55,
        "willing_self_retention_for_lower_premium": 47,
        "sustainability_focus": 36,
        "always_picks_cheapest": 23
      },
      "purchase_criteria_pct": {
        "price_performance": 78,
        "insurance_premium": 46,
        "comprehensive_product": 46,
        "flexible_product": 44,
        "prior_positive_experience": 43,
        "advisor_competence": 42,
        "transparent_product_info": 35,
        "advisor_familiarity": 32,
        "relevant_add_on_services": 24,
        "digital_services_available": 24,
        "company_image": 24,
        "recommendation": 23,
        "advisor_proximity": 16,
        "online_purchase_option": 11,
        "sustainability": 6
      },
      "information_channels_pct": {
        "personal_advisor_broker": 56,
        "online_comparison_platforms": 44,
        "insurer_websites": 37,
        "family_and_friends": 30,
        "google_search": 30,
        "friends_acquaintances": 27,
        "physical_branch": 18,
        "customer_service": 18
      },
      "channel_preference_per_journey_step_pct_dominant_channel": {
        "info_gathering": {
          "channel": "self_online",
          "value": 58
        },
        "offer_request": {
          "channel": "via_advisor",
          "value": 59
        },
        "comparison": {
          "channel": "self_online",
          "value": 74
        },
        "consultation": {
          "channel": "via_advisor",
          "value": 90
        },
        "purchase": {
          "channel": "via_advisor",
          "value": 78
        },
        "contract_questions": {
          "channel": "self_online",
          "value": 40
        },
        "personal_info_update": {
          "channel": "self_online",
          "value": 88
        },
        "contract_modification": {
          "channel": "via_advisor",
          "value": 48
        },
        "contract_cancellation": {
          "channel": "self_online",
          "value": 73
        },
        "payments_payouts": {
          "channel": "self_online",
          "value": 82
        },
        "claim_reporting": {
          "channel": "self_online",
          "value": 57
        },
        "claim_status": {
          "channel": "self_online",
          "value": 85
        }
      },
      "purchase_split_pct": {
        "info_and_purchase_in_person": 43,
        "info_online_purchase_in_person": 38,
        "info_and_purchase_online": 11,
        "info_in_person_purchase_online": 8,
        "summary_purchase_in_person": 81,
        "summary_purchase_online": 19
      },
      "online_behavior": {
        "ever_purchased_insurance_online_pct": 34,
        "likely_to_purchase_online_next_3y_pct": 22,
        "customer_portal_registered_pct": 54,
        "customer_portal_active_last_12_months_pct": 40,
        "top_products_likely_for_online_purchase": [
          {"product": "travel", "pct": 30},
          {"product": "electronics", "pct": 19},
          {"product": "vehicle_liability", "pct": 18},
          {"product": "pet", "pct": 17},
          {"product": "legal_protection", "pct": 16}
        ]
      },
      "media_usage_daily_top_pct": {
        "messenger_services": 91,
        "search_engines": 89,
        "social_media": 76,
        "radio": 58,
        "video_streaming": 52
      },
      "life_events_last_5_years_pct": {
        "minor_physical_complaints": 71,
        "minor_psychological_strain": 45,
        "started_saving_more": 38,
        "moved_home": 33,
        "hospitalization_last_3y": 32,
        "salary_jump": 30,
        "started_investing": 25,
        "started_financial_planning_for_future": 20
      },
      "life_plans_next_3_years_pct": {
        "more_sports": 43,
        "buying_car": 40,
        "losing_weight": 39,
        "saving_more": 32,
        "stress_reduction": 29,
        "diet_change": 22,
        "increased_preventive_checkups": 22,
        "financial_planning_for_future": 20,
        "increased_investing": 20,
        "job_change": 17,
        "career_promotion": 16
      },
      "behavior_and_attitudes": [
        "Hybrid type: combines digital channels with personal advisory",
        "Researches independently (online, comparison)",
        "Wants reassurance through personal advisor for important decisions",
        "Considers insurance important but only deals with it 'as much as necessary'",
        "Places high value on trust and competence of advisor"
      ],
      "needs": [
        "Flexible and tailored products",
        "Broad coverage and add-ons (especially health)",
        "Strong price-performance balance (very important)",
        "Intuitive digital services (app, customer portal)",
        "Support during life events (family, finance, health)"
      ],
      "pain_points": [
        "Overly complex or opaque products",
        "Lack of individualization (one-size-fits-all)",
        "Poor advisory or lack of trust",
        "Too many steps that work neither digitally nor in person"
      ],
      "preferred_channels": {
        "research": [
          "Google",
          "comparison platforms",
          "insurer websites"
        ],
        "management": [
          "apps",
          "customer portal"
        ],
        "purchase_and_consultation": [
          "personal advisor (in person)"
        ],
        "communication": [
          "mix of digital and personal"
        ]
      },
      "online_funnel_behavior_hypotheses": {
        "primary_drop_off_step": "initial_price_display",
        "behavioral_signals_likely": [
          "long dwell time on price comparison table",
          "repeated tariff hover/click without selection",
          "backwards navigation after seeing 'advisory required' on Opt. Plus / Premium",
          "opens external browser tab (likely comparison search)"
        ],
        "intended_outcome": "wanted to research online but complete with advisor later",
        "best_coach_interventions": [
          "Surface market comparison ('Optimal is below 80% of comparable Privatarzt tariffs')",
          "Reframe price psychologically (€68/month ≈ €2.20/day)",
          "Offer term explanations on hover for unfamiliar concepts",
          "Smooth handoff to advisor booking when intent is unclear — counts as conversion"
        ]
      }
    },
    "segment_2": {
      "id": "segment_2",
      "name_short": "Online Affine",
      "name_full": "Die Online Affinen",
      "sample_size": 688,
      "persona_archetype": {
        "name": "Franz Huber",
        "age": 40,
        "location": "Vienna, strongly urban",
        "life_phase": "Employed, often single or in partnership",
        "occupation": "Service-sector employee",
        "typical_quote": "I want to handle everything online — fast, simple, and transparent."
      },
      "market_size_persons": 1105000,
      "market_share_pct": 17,
      "demographics": {
        "age_mean": 43.1,
        "age_distribution_pct": {
          "18_29": 24,
          "30_39": 22,
          "40_49": 20,
          "50_59": 17,
          "60_75": 18
        },
        "female_pct": 44,
        "male_pct": 55,
        "diverse_pct": 1,
        "income_monthly_eur": 3692,
        "income_label": "average",
        "education": {
          "with_matura_pct": 47,
          "without_matura_pct": 53,
          "matura_significantly_above_average": true
        },
        "urbanity": {
          "city_pct": 57,
          "intermediate_pct": 13,
          "countryside_pct": 31,
          "strongly_urban_significantly_above_average": true
        },
        "regional_distribution_pct": {
          "vienna": 41,
          "lower_austria": 16,
          "upper_austria": 12,
          "styria": 11,
          "tyrol": 7,
          "carinthia": 4,
          "vorarlberg": 2,
          "burgenland": 2
        },
        "household": {
          "single_pct": 31,
          "two_person_pct": 36,
          "three_person_pct": 18,
          "four_person_pct": 10,
          "five_plus_pct": 4,
          "in_partnership_pct": 57,
          "single_divorced_widowed_pct": 43,
          "with_children_pct": 27
        },
        "housing": {
          "apartment_pct": 64,
          "house_pct": 35,
          "ownership_pct": 40,
          "rent_pct": 59,
          "owned_apartment_pct": 15,
          "owned_house_pct": 24
        },
        "employment": {
          "employee_pct": 60,
          "retired_pct": 15
        },
        "transport_primary_pct": {
          "car": 40,
          "public_transport": 32
        },
        "vehicle_ownership_pct": {
          "car_combustion": 58,
          "bicycle": 32,
          "e_bicycle": 11,
          "motorcycle": 7,
          "e_car": 7
        }
      },
      "financial_assets_pct": {
        "securities": 33,
        "life_insurance_pension": 32,
        "gold_precious_metals": 23,
        "building_savings": 23,
        "crypto": 14,
        "real_estate": 14,
        "valuables": 13,
        "additional_real_estate": 9
      },
      "insurance_behavior": {
        "current_products_owned": 3.8,
        "new_purchase_intent_3y_products": 1.5,
        "kv_ownership_pct": 25,
        "kv_purchase_intent_3y_pct": 16,
        "switch_willingness_pct": 16,
        "general_attitude_positive_pct": 46,
        "monthly_insurance_spend_eur": 166.8,
        "net_promoter_score": 1,
        "uniqa_customer_pct": 24,
        "uniqa_main_insured_pct": 14,
        "advisor_type_pct": {
          "employed_insurance_advisor": 33,
          "independent_broker": 12,
          "general_agent": 3,
          "no_advisor": 47
        },
        "top_3_main_insurers_pct": {
          "uniqa": 14,
          "wiener_staedtische": 11,
          "allianz": 10
        },
        "current_holdings_pct": {
          "household": 72,
          "vehicle_liability": 52,
          "legal_protection": 40,
          "vehicle_comprehensive": 29,
          "life_pension": 29,
          "home_ownership": 28,
          "accident": 26,
          "health": 25,
          "death": 18,
          "travel": 13,
          "electronics": 10,
          "occupational_disability": 9,
          "motorcycle_moped": 8,
          "pet": 8,
          "bicycle_scooter": 3,
          "cyber": 3,
          "care": 2
        },
        "new_purchase_likelihood_3y_pct": {
          "household": 11,
          "vehicle_liability": 10,
          "legal_protection": 10,
          "vehicle_comprehensive": 8,
          "life_pension": 13,
          "home_ownership": 7,
          "accident": 8,
          "health": 16,
          "death": 13,
          "travel": 12,
          "electronics": 8,
          "occupational_disability": 10,
          "motorcycle_moped": 2,
          "pet": 6,
          "bicycle_scooter": 2,
          "cyber": 4,
          "care": 5
        }
      },
      "decision_drivers_pct": {
        "price_performance_ratio": 85,
        "compares_multiple_offers": 82,
        "values_apps_and_portals": 79,
        "tailored_products": 73,
        "low_engagement_only_what_needed": 63,
        "advised_at_life_events": 51,
        "willing_self_retention_for_lower_premium": 48,
        "single_insurer_preference": 47,
        "broad_life_coverage": 45,
        "sustainability_focus": 45,
        "personal_advisor_trust": 44,
        "always_picks_cheapest": 42
      },
      "purchase_criteria_pct": {
        "price_performance": 67,
        "insurance_premium": 43,
        "online_purchase_option": 36,
        "comprehensive_product": 35,
        "transparent_product_info": 33,
        "flexible_product": 32,
        "prior_positive_experience": 27,
        "digital_services_available": 25,
        "relevant_add_on_services": 21,
        "company_image": 19,
        "recommendation": 18,
        "advisor_competence": 16,
        "advisor_familiarity": 12,
        "advisor_proximity": 6,
        "sustainability": 6
      },
      "information_channels_pct": {
        "online_comparison_platforms": 52,
        "insurer_websites": 42,
        "google_search": 37,
        "family_and_friends": 24,
        "personal_advisor_broker": 19,
        "friends_acquaintances": 19,
        "customer_service": 13,
        "physical_branch": 12
      },
      "channel_preference_per_journey_step_pct_dominant_channel": {
        "info_gathering": {
          "channel": "self_online",
          "value": 90
        },
        "offer_request": {
          "channel": "self_online",
          "value": 86
        },
        "comparison": {
          "channel": "self_online",
          "value": 94
        },
        "consultation": {
          "channel": "self_online",
          "value": 61
        },
        "purchase": {
          "channel": "self_online",
          "value": 89
        },
        "contract_questions": {
          "channel": "self_online",
          "value": 72
        },
        "personal_info_update": {
          "channel": "self_online",
          "value": 94
        },
        "contract_modification": {
          "channel": "self_online",
          "value": 89
        },
        "contract_cancellation": {
          "channel": "self_online",
          "value": 92
        },
        "payments_payouts": {
          "channel": "self_online",
          "value": 92
        },
        "claim_reporting": {
          "channel": "self_online",
          "value": 85
        },
        "claim_status": {
          "channel": "self_online",
          "value": 90
        }
      },
      "purchase_split_pct": {
        "info_and_purchase_online": 59,
        "info_online_purchase_in_person": 16,
        "info_and_purchase_in_person": 15,
        "info_in_person_purchase_online": 10,
        "summary_purchase_online": 69,
        "summary_purchase_in_person": 31
      },
      "online_behavior": {
        "ever_purchased_insurance_online_pct": 64,
        "likely_to_purchase_online_next_3y_pct": 43,
        "customer_portal_registered_pct": 47,
        "customer_portal_active_last_12_months_pct": 31,
        "top_products_likely_for_online_purchase": [
          {"product": "household", "pct": 30},
          {"product": "travel", "pct": 30},
          {"product": "vehicle_liability", "pct": 29},
          {"product": "legal_protection", "pct": 26},
          {"product": "vehicle_comprehensive", "pct": 20}
        ]
      },
      "media_usage_daily_top_pct": {
        "search_engines": 86,
        "messenger_services": 85,
        "social_media": 72,
        "video_streaming": 55,
        "online_news_portals": 52
      },
      "life_events_last_5_years_pct": {
        "minor_physical_complaints": 61,
        "moved_home": 40,
        "minor_psychological_strain": 39,
        "hospitalization_last_3y": 31,
        "started_investing": 21,
        "first_car": 20
      },
      "life_plans_next_3_years_pct": {
        "buying_car": 45,
        "moving_home": 36,
        "more_sports": 30,
        "job_change": 17,
        "increased_investing": 16
      },
      "behavior_and_attitudes": [
        "Digital-first: handles as much as possible online by themselves",
        "Highly independent and information-driven",
        "Active user of comparison platforms and websites",
        "Low advisor loyalty — often no fixed contact person (47% no advisor)",
        "Pragmatic view of insurance ('a product like any other')"
      ],
      "needs": [
        "Simple, fast digital processes (research to purchase)",
        "Clear, transparent product information",
        "Strong price-performance ratio with price sensitivity",
        "Self-service capability for everything",
        "Digital tools like apps and customer portals"
      ],
      "pain_points": [
        "Complex and hard-to-understand offers",
        "Opaque prices or terms",
        "Media breaks (forced switch from online to offline)",
        "Dependency on advisors / long processes"
      ],
      "preferred_channels": {
        "research": [
          "comparison platforms (very important)",
          "insurer websites",
          "Google search"
        ],
        "management": [
          "customer portals",
          "apps"
        ],
        "purchase_and_consultation": [
          "online self-service"
        ],
        "personal_advisory_share": "minimal"
      },
      "online_funnel_behavior_hypotheses": {
        "primary_drop_off_step": "final_price_after_health_questions",
        "behavioral_signals_likely": [
          "fast progression through early steps",
          "comparison-tab opens (visible session gaps)",
          "sticks on final price screen when result exceeds expectation",
          "may click 'cancel' if the price-performance ratio appears unfavorable"
        ],
        "intended_outcome": "intends to complete online if price-performance is right",
        "best_coach_interventions": [
          "Show value justification when final price diverges from initial estimate",
          "Surface comparable lower-priced tariff with explicit feature comparison",
          "Offer pause-and-resume function (save progress, no advisor needed)",
          "Avoid pushing toward advisor handoff — this segment dislikes it"
        ]
      }
    },
    "segment_3": {
      "id": "segment_3",
      "name_short": "Service Affine",
      "name_full": "Die Kundenservice Affinen",
      "sample_size": 546,
      "persona_archetype": {
        "name": "Peter Wagner",
        "age": 35,
        "location": "Mix of urban and rural",
        "life_phase": "Employed, often in stable partnership, sometimes family",
        "occupation": "Operational / service-oriented employee",
        "typical_quote": "I don't want to deal with this — just tell me what I need."
      },
      "market_size_persons": 910000,
      "market_share_pct": 14,
      "demographics": {
        "age_mean": 40.9,
        "age_distribution_pct": {
          "18_29": 28,
          "30_39": 24,
          "40_49": 17,
          "50_59": 16,
          "60_75": 15
        },
        "female_pct": 51,
        "male_pct": 48,
        "income_monthly_eur": 3557,
        "income_label": "below_average_to_average",
        "education": {
          "with_matura_pct": 38,
          "without_matura_pct": 62
        },
        "urbanity": {
          "city_pct": 41,
          "intermediate_pct": 16,
          "countryside_pct": 44
        },
        "regional_distribution_pct": {
          "vienna": 28,
          "lower_austria": 16,
          "upper_austria": 16,
          "tyrol": 10,
          "styria": 10,
          "salzburg": 7,
          "carinthia": 6,
          "burgenland": 3,
          "vorarlberg": 3
        },
        "household": {
          "single_pct": 26,
          "two_person_pct": 35,
          "three_person_pct": 17,
          "four_person_pct": 14,
          "five_plus_pct": 7,
          "in_partnership_pct": 59,
          "single_divorced_widowed_pct": 41,
          "with_children_pct": 30
        },
        "housing": {
          "apartment_pct": 56,
          "house_pct": 41,
          "ownership_pct": 44,
          "rent_pct": 52,
          "owned_apartment_pct": 18,
          "owned_house_pct": 26
        },
        "employment": {
          "employee_pct": 60,
          "retired_pct": 15
        },
        "transport_primary_pct": {
          "car": 47,
          "public_transport": 22
        },
        "vehicle_ownership_pct": {
          "car_combustion": 62,
          "bicycle": 26,
          "e_bicycle": 8,
          "e_car": 6,
          "motorcycle": 4
        }
      },
      "financial_assets_pct": {
        "life_insurance_pension": 35,
        "building_savings": 27,
        "securities": 22,
        "gold_precious_metals": 19,
        "real_estate": 16,
        "crypto": 13,
        "valuables": 11,
        "additional_real_estate": 10
      },
      "insurance_behavior": {
        "current_products_owned": 3.5,
        "new_purchase_intent_3y_products": 1.3,
        "kv_ownership_pct": 21,
        "kv_purchase_intent_3y_pct": 13,
        "switch_willingness_pct": 24,
        "general_attitude_positive_pct": 49,
        "monthly_insurance_spend_eur": 167.3,
        "net_promoter_score": -6,
        "uniqa_customer_pct": 25,
        "uniqa_main_insured_pct": 15,
        "advisor_type_pct": {
          "employed_insurance_advisor": 39,
          "independent_broker": 18,
          "general_agent": 6,
          "no_advisor": 28
        },
        "top_3_main_insurers_pct": {
          "uniqa": 15,
          "allianz": 14,
          "generali": 10
        },
        "current_holdings_pct": {
          "household": 57,
          "vehicle_liability": 52,
          "legal_protection": 34,
          "vehicle_comprehensive": 28,
          "home_ownership": 28,
          "accident": 27,
          "life_pension": 24,
          "health": 21,
          "death": 19,
          "travel": 13,
          "occupational_disability": 12,
          "electronics": 10,
          "pet": 9,
          "motorcycle_moped": 7,
          "care": 3,
          "cyber": 3,
          "bicycle_scooter": 3
        },
        "new_purchase_likelihood_3y_pct": {
          "household": 10,
          "vehicle_liability": 9,
          "legal_protection": 8,
          "vehicle_comprehensive": 8,
          "home_ownership": 6,
          "accident": 7,
          "life_pension": 10,
          "health": 13,
          "death": 10,
          "travel": 9,
          "occupational_disability": 11,
          "electronics": 8,
          "pet": 5,
          "motorcycle_moped": 3,
          "care": 6,
          "cyber": 6,
          "bicycle_scooter": 2
        }
      },
      "decision_drivers_pct": {
        "tailored_products": 65,
        "price_performance_ratio": 63,
        "compares_multiple_offers": 61,
        "advised_at_life_events": 58,
        "personal_advisor_trust": 56,
        "low_engagement_only_what_needed": 55,
        "single_insurer_preference": 50,
        "broad_life_coverage": 49,
        "values_apps_and_portals": 49,
        "sustainability_focus": 49,
        "willing_self_retention_for_lower_premium": 46,
        "always_picks_cheapest": 36
      },
      "purchase_criteria_pct": {
        "price_performance": 44,
        "flexible_product": 24,
        "prior_positive_experience": 24,
        "insurance_premium": 23,
        "comprehensive_product": 23,
        "recommendation": 20,
        "transparent_product_info": 19,
        "advisor_competence": 19,
        "company_image": 18,
        "advisor_familiarity": 16,
        "advisor_proximity": 16,
        "online_purchase_option": 13,
        "relevant_add_on_services": 13,
        "digital_services_available": 9,
        "sustainability": 8
      },
      "information_channels_pct": {
        "online_comparison_platforms": 27,
        "personal_advisor_broker": 23,
        "family_and_friends": 23,
        "insurer_websites": 21,
        "friends_acquaintances": 19,
        "customer_service": 19,
        "physical_branch": 19,
        "google_search": 19
      },
      "channel_preference_per_journey_step_pct_dominant_channel": {
        "info_gathering": {
          "channel": "customer_service",
          "value": 61
        },
        "offer_request": {
          "channel": "customer_service",
          "value": 62
        },
        "comparison": {
          "channel": "customer_service",
          "value": 51
        },
        "consultation": {
          "channel": "customer_service",
          "value": 61
        },
        "purchase": {
          "channel": "customer_service",
          "value": 59
        },
        "contract_questions": {
          "channel": "customer_service",
          "value": 63
        },
        "personal_info_update": {
          "channel": "customer_service",
          "value": 59
        },
        "contract_modification": {
          "channel": "customer_service",
          "value": 65
        },
        "contract_cancellation": {
          "channel": "customer_service",
          "value": 61
        },
        "payments_payouts": {
          "channel": "customer_service",
          "value": 61
        },
        "claim_reporting": {
          "channel": "customer_service",
          "value": 62
        },
        "claim_status": {
          "channel": "customer_service",
          "value": 64
        }
      },
      "purchase_split_pct": {
        "info_and_purchase_in_person": 40,
        "info_online_purchase_in_person": 25,
        "info_in_person_purchase_online": 18,
        "info_and_purchase_online": 16,
        "summary_purchase_in_person": 66,
        "summary_purchase_online": 34
      },
      "online_behavior": {
        "ever_purchased_insurance_online_pct": 39,
        "likely_to_purchase_online_next_3y_pct": 29,
        "customer_portal_registered_pct": 32,
        "customer_portal_active_last_12_months_pct": 21,
        "top_products_likely_for_online_purchase": [
          {"product": "vehicle_liability", "pct": 18},
          {"product": "travel", "pct": 14},
          {"product": "electronics", "pct": 12},
          {"product": "vehicle_comprehensive", "pct": 12},
          {"product": "household", "pct": 11},
          {"product": "cyber", "pct": 11}
        ]
      },
      "media_usage_daily_top_pct": {
        "messenger_services": 75,
        "search_engines": 71,
        "social_media": 66,
        "radio": 49,
        "video_streaming": 49
      },
      "life_events_last_5_years_pct": {
        "minor_physical_complaints": 45,
        "moved_home": 45,
        "hospitalization_last_3y": 43,
        "salary_jump": 30,
        "minor_psychological_strain": 30,
        "first_car": 29,
        "inheritance": 20,
        "had_children_last_6y": 18,
        "took_care_of_family_member": 16,
        "career_promotion": 15
      },
      "life_plans_next_3_years_pct": {
        "buying_car": 53,
        "moving_home": 45,
        "buying_pet": 17,
        "job_change": 16,
        "moving_into_ownership": 16,
        "inheritance": 15
      },
      "behavior_and_attitudes": [
        "Service-oriented: does not want to manage things alone",
        "Prefers simple solutions and clear guidance",
        "Low interest in actively engaging with insurance",
        "Advisor skepticism, yet need for help",
        "Sees insurance as a necessary topic, not a personal interest"
      ],
      "needs": [
        "Simple, understandable products",
        "Clear guidance through customer service",
        "Support at all journey steps (advisory, purchase, changes)",
        "Strong price-performance ratio",
        "Reassurance that 'everything is taken care of' without personal effort"
      ],
      "pain_points": [
        "Overly complex products or unclear information",
        "Too many decisions to make alone",
        "Uncertainty about correctness of own choices",
        "Negative experiences with impersonal or hard-to-reach service"
      ],
      "preferred_channels": {
        "consultation_and_management": [
          "customer service phone",
          "email",
          "messenger"
        ],
        "research": [
          "limited use of digital channels"
        ],
        "comparison_platforms": "rarely_used"
      },
      "online_funnel_behavior_hypotheses": {
        "primary_drop_off_step": "earlier_steps_or_initial_price",
        "behavioral_signals_likely": [
          "early signs of overwhelm: long dwell time on early form steps",
          "multiple back-navigations",
          "filling fields hesitantly or incorrectly",
          "abandonment before reaching tariff selection — 'this is too much, I'll call'"
        ],
        "intended_outcome": "did not actually plan to complete online — arrived via search but prefers phone or in-person",
        "best_coach_interventions": [
          "Detect overwhelm early (high time-on-task with low progress)",
          "Offer customer service handoff proactively and warmly",
          "Simplify form fields drastically when overwhelm is detected",
          "Acknowledge that not completing online is okay — provide easy phone callback option",
          "Conversion = qualified service contact for this segment, not online purchase"
        ]
      }
    }
  },
  "intervention_taxonomy_suggestions": {
    "description": "Non-exhaustive list of intervention types teams may use, extend, or replace.",
    "categories": {
      "explanation": [
        "tooltip_on_unfamiliar_term",
        "inline_term_glossary",
        "expandable_concept_explainer"
      ],
      "reassurance": [
        "market_comparison_signal",
        "trust_badge",
        "money_back_guarantee_reminder",
        "psychological_price_reframe"
      ],
      "alternative_offering": [
        "suggest_cheaper_tariff",
        "suggest_tariff_with_fewer_addons",
        "remove_friction_step"
      ],
      "handoff": [
        "advisor_booking_proactive",
        "callback_request_friendly",
        "live_chat_proactive_open",
        "save_progress_resume_later"
      ],
      "personalization": [
        "simplify_form_fields_for_overwhelmed_user",
        "skip_optional_steps_when_intent_clear",
        "lengthen_explanations_when_uncertainty_detected"
      ]
    }
  },
  "usage_notes_for_teams": [
    "Use these personas as starting prompts for persona bots — do not just paste the JSON, write a system prompt that references the relevant attributes.",
    "If you create persona sub-variants, declare them clearly and explain why.",
    "The 'online_funnel_behavior_hypotheses' are explicitly hypotheses — your job is to test them, not assume them as truth.",
    "The 'online_funnel_traffic_share' is an estimate, not hard data. Treat it as a prior, not ground truth.",
    "Quantitative values are population-level statistics. Persona bots should reflect the segment archetype, not match every percentage exactly.",
    "channel_preference_per_journey_step_pct_dominant_channel shows the MOST PREFERRED channel per step (with %). Other channels (advisor/customer service/online) take the remaining share but specific values are not separately published."
  ]
}