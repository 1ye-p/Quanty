/**
 * i18n mapping for dynamic sizer/policy registry data.
 *
 * Keys are the registry names served by the backend (`/risk/sizers`,
 * `/risk/policies` in `python/cquant/api_server/routes/risk.py`). The JSON
 * config still stores the English registry name — this mapping is
 * display-only. Unmapped entries fall back to the backend-provided English
 * name/description.
 */

export interface ParamLabel {
  labelKey: string
}

export interface RegistryLabel {
  nameKey: string
  descKey: string
  params?: Record<string, ParamLabel>
}

export const SIZER_LABELS: Record<string, RegistryLabel> = {
  equal_weight: {
    nameKey: 'common.sizer.equal_weight.name',
    descKey: 'common.sizer.equal_weight.desc',
  },
  kelly: {
    nameKey: 'common.sizer.kelly.name',
    descKey: 'common.sizer.kelly.desc',
    params: {
      fraction: {
        labelKey: 'common.sizer.param.fraction.name',
      },
    },
  },
  mvo: {
    nameKey: 'common.sizer.mvo.name',
    descKey: 'common.sizer.mvo.desc',
    params: {
      risk_free_rate: {
        labelKey: 'common.sizer.param.risk_free_rate.name',
      },
      long_only: {
        labelKey: 'common.sizer.param.long_only.name',
      },
    },
  },
  target_vol: {
    nameKey: 'common.sizer.target_vol.name',
    descKey: 'common.sizer.target_vol.desc',
    params: {
      target_vol: {
        labelKey: 'common.sizer.param.target_vol.name',
      },
    },
  },
  vol_parity: {
    nameKey: 'common.sizer.vol_parity.name',
    descKey: 'common.sizer.vol_parity.desc',
  },
  black_litterman: {
    nameKey: 'common.sizer.black_litterman.name',
    descKey: 'common.sizer.black_litterman.desc',
    params: {
      tau: {
        labelKey: 'common.sizer.param.tau.name',
      },
      risk_free_rate: {
        labelKey: 'common.sizer.param.risk_free_rate.name',
      },
    },
  },
}

export const POLICY_LABELS: Record<string, RegistryLabel> = {
  fixed_stop_loss: {
    nameKey: 'common.risk_policy.fixed_stop_loss.name',
    descKey: 'common.risk_policy.fixed_stop_loss.desc',
    params: {
      stop_pct: {
        labelKey: 'common.risk_policy.param.stop_pct.name',
      },
    },
  },
  trailing_stop_loss: {
    nameKey: 'common.risk_policy.trailing_stop_loss.name',
    descKey: 'common.risk_policy.trailing_stop_loss.desc',
    params: {
      trailing_pct: {
        labelKey: 'common.risk_policy.param.trailing_pct.name',
      },
    },
  },
  atr_stop_loss: {
    nameKey: 'common.risk_policy.atr_stop_loss.name',
    descKey: 'common.risk_policy.atr_stop_loss.desc',
    params: {
      n_atr: {
        labelKey: 'common.risk_policy.param.n_atr.name',
      },
    },
  },
  drawdown_breaker: {
    nameKey: 'common.risk_policy.drawdown_breaker_reg.name',
    descKey: 'common.risk_policy.drawdown_breaker_reg.desc',
    params: {
      max_drawdown: {
        labelKey: 'common.risk_policy.param.max_drawdown.name',
      },
    },
  },
  position_limit: {
    nameKey: 'common.risk_policy.position_limit_reg.name',
    descKey: 'common.risk_policy.position_limit_reg.desc',
    params: {
      max_position_pct: {
        labelKey: 'common.risk_policy.param.max_position_pct.name',
      },
    },
  },
  leverage_limit: {
    nameKey: 'common.risk_policy.leverage_limit_reg.name',
    descKey: 'common.risk_policy.leverage_limit_reg.desc',
    params: {
      max_gross_leverage: {
        labelKey: 'common.risk_policy.param.max_gross_leverage.name',
      },
    },
  },
  sector_limit: {
    nameKey: 'common.risk_policy.sector_limit.name',
    descKey: 'common.risk_policy.sector_limit.desc',
    params: {
      max_sector_pct: {
        labelKey: 'common.risk_policy.param.max_sector_pct.name',
      },
      sector_map: {
        labelKey: 'common.risk_policy.param.sector_map.name',
      },
    },
  },
  max_holding_days: {
    nameKey: 'common.risk_policy.max_holding_days.name',
    descKey: 'common.risk_policy.max_holding_days.desc',
    params: {
      max_days: {
        labelKey: 'common.risk_policy.param.max_days.name',
      },
    },
  },
  factor_exposure_limit: {
    nameKey: 'common.risk_policy.factor_exposure_limit.name',
    descKey: 'common.risk_policy.factor_exposure_limit.desc',
    params: {
      factor_limits: {
        labelKey: 'common.risk_policy.param.factor_limits.name',
      },
    },
  },
}

/** Resolve a localized display name for a registry entry, with English fallback. */
export function sizerDisplayName(t: (k: string) => string, name: string, fallback: string): string {
  const labels = SIZER_LABELS[name]
  return labels ? t(labels.nameKey) : fallback
}

export function sizerDisplayDesc(t: (k: string) => string, name: string, fallback: string): string {
  const labels = SIZER_LABELS[name]
  return labels ? t(labels.descKey) : fallback
}

export function policyDisplayName(t: (k: string) => string, name: string, fallback: string): string {
  const labels = POLICY_LABELS[name]
  return labels ? t(labels.nameKey) : fallback
}

export function policyDisplayDesc(t: (k: string) => string, name: string, fallback: string): string {
  const labels = POLICY_LABELS[name]
  return labels ? t(labels.descKey) : fallback
}

/** Resolve a localized param label (falls back to the backend description). */
export function paramLabel(
  registry: 'sizer' | 'policy',
  entryName: string,
  paramKey: string,
  t: (k: string) => string,
  fallback: string,
): string {
  const labels = registry === 'sizer' ? SIZER_LABELS[entryName] : POLICY_LABELS[entryName]
  const param = labels?.params?.[paramKey]
  return param ? t(param.labelKey) : fallback
}
