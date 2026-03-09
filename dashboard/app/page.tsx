"use client";

import { useEffect, useState, useCallback } from "react";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import { HourlyChart } from "@/components/charts/hourly-chart";
import { MetricTimeSeriesChart } from "@/components/charts/metric-timeseries-chart";
import {
  fetchDailyStats,
  fetchHourlyData,
  fetchCategoryDaily,
  fetchLabourCost,
  fetchDailyLabour,
  aggregateStats,
  aggregateCategoryStats,
  type DailyStats,
  type HourlyData,
  type CategoryDailyData,
  type DailyLabour,
} from "@/lib/queries/overview";
import {
  type PeriodType,
  type ComparisonType,
  resolvePeriodRange,
  resolveComparisonRange,
  getComparisonDate,
} from "@/lib/dates";
import { formatCurrency, formatPercent, formatNumber, calcChange } from "@/lib/format";
import { motion } from "framer-motion";

export default function OverviewPage() {
  const [period, setPeriod] = useState<PeriodType>("this_month");
  const [comparison, setComparison] = useState<ComparisonType>("prior_period");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [loading, setLoading] = useState(true);

  // Data states
  const [currentStats, setCurrentStats] = useState<ReturnType<typeof aggregateStats> | null>(null);
  const [compStats, setCompStats] = useState<ReturnType<typeof aggregateStats> | null>(null);
  const [dailyRows, setDailyRows] = useState<DailyStats[]>([]);
  const [compDailyRows, setCompDailyRows] = useState<DailyStats[]>([]);
  const [hourlyData, setHourlyData] = useState<HourlyData[]>([]);
  const [compHourlyData, setCompHourlyData] = useState<HourlyData[]>([]);
  const [categoryData, setCategoryData] = useState<CategoryDailyData[]>([]);
  const [compCategoryData, setCompCategoryData] = useState<CategoryDailyData[]>([]);
  const [labourCost, setLabourCost] = useState(0);
  const [compLabourCost, setCompLabourCost] = useState(0);
  const [dailyLabour, setDailyLabour] = useState<DailyLabour[]>([]);
  const [compDailyLabour, setCompDailyLabour] = useState<DailyLabour[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Resolve date ranges from period selection
      const currentRange = resolvePeriodRange(period, customStart, customEnd);
      const compRange = resolveComparisonRange(currentRange, comparison, period);

      const { startDate, endDate } = currentRange;
      const { startDate: compStart, endDate: compEnd } = compRange;

      // Fetch all data in parallel
      const [
        dRows,
        cDRows,
        hourly,
        compHourly,
        catData,
        compCatData,
        labour,
        compLabour,
        dLabour,
        cDLabour,
      ] = await Promise.all([
        fetchDailyStats(startDate, endDate),
        fetchDailyStats(compStart, compEnd),
        period === "today" ? fetchHourlyData(startDate) : Promise.resolve([]),
        period === "today"
          ? fetchHourlyData(getComparisonDate(startDate, "prior_same_weekday"))
          : Promise.resolve([]),
        fetchCategoryDaily(startDate, endDate),
        fetchCategoryDaily(compStart, compEnd),
        fetchLabourCost(startDate, endDate),
        fetchLabourCost(compStart, compEnd),
        fetchDailyLabour(startDate, endDate),
        fetchDailyLabour(compStart, compEnd),
      ]);

      setDailyRows(dRows);
      setCompDailyRows(cDRows);
      setCurrentStats(aggregateStats(dRows));
      setCompStats(aggregateStats(cDRows));
      setHourlyData(hourly);
      setCompHourlyData(compHourly);
      setCategoryData(catData);
      setCompCategoryData(compCatData);
      setLabourCost(labour);
      setCompLabourCost(compLabour);
      setDailyLabour(dLabour);
      setCompDailyLabour(cDLabour);
    } catch (err) {
      console.error("Failed to load overview data:", err);
    } finally {
      setLoading(false);
    }
  }, [period, comparison, customStart, customEnd]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const cs = currentStats;
  const ps = compStats;

  // If comparison period has no transactions, it means no data exists
  // (e.g. comparing to a period before the store opened)
  const noCompData = !ps || ps.transactions === 0;
  const noCompLabour = noCompData || compLabourCost === 0;

  const labourRatio = cs && cs.netSales > 0 ? (labourCost / cs.netSales) * 100 : 0;
  const compLabourRatio =
    ps && ps.netSales > 0 ? (compLabourCost / ps.netSales) * 100 : 0;

  const catAgg = aggregateCategoryStats(categoryData);
  const compCatAgg = aggregateCategoryStats(compCategoryData);
  const noCompCat = compCatAgg.cafeNetSales === 0 && compCatAgg.retailNetSales === 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8"
    >
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-[28px] font-bold text-foreground">Overview</h1>
      </div>

      {/* Period Selector */}
      <PeriodSelector
        period={period}
        comparison={comparison}
        customStart={customStart}
        customEnd={customEnd}
        onPeriodChange={setPeriod}
        onComparisonChange={setComparison}
        onCustomRangeChange={(s, e) => {
          setCustomStart(s);
          setCustomEnd(e);
        }}
      />

      {/* Performance KPIs — Hourly Chart + 6 cards */}
      <section>
        {/* Hourly chart (only for "today" period) */}
        {period === "today" && hourlyData.length > 0 && (
          <div className="mb-6">
            <HourlyChart
              data={hourlyData}
              comparisonData={compHourlyData}
              title="Transactions per hour"
            />
          </div>
        )}

        {/* 6 KPI Cards — 2 rows × 3 cols */}
        <div className="grid grid-cols-3 gap-5">
          <KpiCard
            label="Net Sales"
            value={cs?.netSales ?? 0}
            formatter={(n) => formatCurrency(n)}
            change={noCompData ? null : calcChange(cs?.netSales ?? 0, ps?.netSales ?? 0)}
            noCompData={noCompData}
            delay={0}
          />
          <KpiCard
            label="Transactions"
            value={cs?.transactions ?? 0}
            formatter={(n) => formatNumber(n)}
            change={noCompData ? null : calcChange(cs?.transactions ?? 0, ps?.transactions ?? 0)}
            noCompData={noCompData}
            delay={1}
          />
          <KpiCard
            label="Average Sale"
            value={cs?.avgSale ?? 0}
            formatter={(n) => formatCurrency(n)}
            change={noCompData ? null : calcChange(cs?.avgSale ?? 0, ps?.avgSale ?? 0)}
            noCompData={noCompData}
            delay={2}
          />
          <KpiCard
            label="Gross Sales"
            value={cs?.grossSales ?? 0}
            formatter={(n) => formatCurrency(n)}
            change={noCompData ? null : calcChange(cs?.grossSales ?? 0, ps?.grossSales ?? 0)}
            noCompData={noCompData}
            delay={3}
          />
          <KpiCard
            label="Labour Cost"
            value={labourCost}
            formatter={(n) => formatCurrency(n)}
            change={noCompLabour ? null : calcChange(labourCost, compLabourCost)}
            noCompData={noCompLabour}
            invertColor
            delay={4}
          />
          <KpiCard
            label="Labour Cost vs Sales %"
            value={labourRatio}
            formatter={(n) => formatPercent(n)}
            change={noCompLabour ? null : calcChange(labourRatio, compLabourRatio)}
            noCompData={noCompLabour}
            invertColor
            subtitle="Target: 25–35%"
            delay={5}
          />
        </div>
      </section>

      {/* Unified Time-Series Chart — switchable metrics */}
      <section>
        <MetricTimeSeriesChart
          dailyStats={dailyRows}
          compDailyStats={compDailyRows}
          categoryData={categoryData}
          compCategoryData={compCategoryData}
          dailyLabour={dailyLabour}
          compDailyLabour={compDailyLabour}
        />

        {/* Category KPIs (Cafe vs Retail breakdown) */}
        <div className="grid grid-cols-3 gap-5 mt-5">
          <KpiCard
            label="Cafe Net Sales"
            value={catAgg.cafeNetSales}
            formatter={(n) => formatCurrency(n)}
            change={noCompCat ? null : calcChange(catAgg.cafeNetSales, compCatAgg.cafeNetSales)}
            noCompData={noCompCat}
            delay={6}
          />
          <KpiCard
            label="Retail Net Sales"
            value={catAgg.retailNetSales}
            formatter={(n) => formatCurrency(n)}
            change={noCompCat ? null : calcChange(catAgg.retailNetSales, compCatAgg.retailNetSales)}
            noCompData={noCompCat}
            delay={7}
          />
          <KpiCard
            label="Total Net Sales"
            value={catAgg.cafeNetSales + catAgg.retailNetSales}
            formatter={(n) => formatCurrency(n)}
            change={
              noCompCat
                ? null
                : calcChange(
                  catAgg.cafeNetSales + catAgg.retailNetSales,
                  compCatAgg.cafeNetSales + compCatAgg.retailNetSales
                )
            }
            noCompData={noCompCat}
            delay={8}
          />
        </div>
      </section>

      {loading && (
        <div className="fixed inset-0 ml-[220px] bg-background/80 flex items-center justify-center z-40">
          <div className="flex items-center gap-3 text-muted-foreground">
            <div className="w-5 h-5 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
            <span className="text-sm">Loading data...</span>
          </div>
        </div>
      )}
    </motion.div>
  );
}
