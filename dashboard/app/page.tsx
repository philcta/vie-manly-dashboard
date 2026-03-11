"use client";

import { useEffect, useState, useCallback } from "react";
import KpiCard from "@/components/kpi-card";
import PeriodSelector from "@/components/period-selector";
import { HourlyChart } from "@/components/charts/hourly-chart";
import { MetricTimeSeriesChart } from "@/components/charts/metric-timeseries-chart";
import { CategoryMarginChart } from "@/components/charts/category-margin-chart";
import {
  fetchDailyStats,
  fetchHourlyData,
  fetchCategoryDaily,
  fetchCategoryDetailDaily,
  fetchLabourCost,
  fetchLabourCostBySide,
  fetchDailyLabour,
  fetchCategorySalesTotals,
  aggregateStats,
  aggregateCategoryStats,
  type DailyStats,
  type HourlyData,
  type CategoryDailyData,
  type DailyLabour,
  type CategorySalesTotal,
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
import { supabase } from "@/lib/supabase";

// ── Types for inventory margins ─────────────────────────────────

interface MarginRow {
  scope_type: string;
  scope: string;
  side: string;
  margin_pct: number;
  product_count: number;
  stock_value: number;
  retail_value: number;
}

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
  const [categoryDetailData, setCategoryDetailData] = useState<CategoryDailyData[]>([]);
  const [labourCost, setLabourCost] = useState(0);
  const [compLabourCost, setCompLabourCost] = useState(0);
  const [dailyLabour, setDailyLabour] = useState<DailyLabour[]>([]);
  const [compDailyLabour, setCompDailyLabour] = useState<DailyLabour[]>([]);
  const [catSalesTotals, setCatSalesTotals] = useState<CategorySalesTotal[]>([]);
  const [compCatSalesTotals, setCompCatSalesTotals] = useState<CategorySalesTotal[]>([]);
  const [labourBySide, setLabourBySide] = useState<{ cafe: number; retail: number }>({ cafe: 0, retail: 0 });
  const [compLabourBySide, setCompLabourBySide] = useState<{ cafe: number; retail: number }>({ cafe: 0, retail: 0 });

  // Inventory margins (pre-computed in Supabase)
  const [marginData, setMarginData] = useState<MarginRow[]>([]);
  const [overallMargin, setOverallMargin] = useState(0);
  const [cafeMargin, setCafeMargin] = useState(0);
  const [retailMargin, setRetailMargin] = useState(0);

  // Historical data for 3/6-month moving averages
  const [historicalStats, setHistoricalStats] = useState<DailyStats[]>([]);
  const [historicalCategoryData, setHistoricalCategoryData] = useState<CategoryDailyData[]>([]);
  const [historicalLabour, setHistoricalLabour] = useState<DailyLabour[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const currentRange = resolvePeriodRange(period, customStart, customEnd);
      const compRange = resolveComparisonRange(currentRange, comparison, period);

      const { startDate, endDate } = currentRange;
      const { startDate: compStart, endDate: compEnd } = compRange;

      // Compute 6-month lookback for moving averages
      const lookbackDate = new Date(startDate);
      lookbackDate.setMonth(lookbackDate.getMonth() - 6);
      const histStart = lookbackDate.toISOString().slice(0, 10);

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
        catSales,
        compCatSales,
        marginsResult,
        histStats,
        histCatData,
        histLabour,
        labSide,
        compLabSide,
        catDetailData,
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
        fetchCategorySalesTotals(startDate, endDate),
        fetchCategorySalesTotals(compStart, compEnd),
        supabase
          .from("inventory_margins")
          .select("scope_type, scope, side, margin_pct, product_count, stock_value, retail_value")
          .eq("source_date", (await supabase.from("inventory_margins").select("source_date").order("source_date", { ascending: false }).limit(1)).data?.[0]?.source_date || ""),
        // Historical data for 3/6-month trailing averages
        fetchDailyStats(histStart, endDate),
        fetchCategoryDaily(histStart, endDate),
        fetchDailyLabour(histStart, endDate),
        fetchLabourCostBySide(startDate, endDate),
        fetchLabourCostBySide(compStart, compEnd),
        fetchCategoryDetailDaily(startDate, endDate),
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
      setCatSalesTotals(catSales);
      setCompCatSalesTotals(compCatSales);
      setHistoricalStats(histStats);
      setHistoricalCategoryData(histCatData);
      setHistoricalLabour(histLabour);
      setLabourBySide(labSide);
      setCompLabourBySide(compLabSide);
      setCategoryDetailData(catDetailData);

      // Process margin data
      const margins = (marginsResult.data || []) as MarginRow[];
      setMarginData(margins);

      const overall = margins.find(m => m.scope_type === "overall");
      const cafe = margins.find(m => m.scope_type === "side" && m.scope === "Cafe");
      const retail = margins.find(m => m.scope_type === "side" && m.scope === "Retail");
      setOverallMargin(overall?.margin_pct ?? 0);
      setCafeMargin(cafe?.margin_pct ?? 0);
      setRetailMargin(retail?.margin_pct ?? 0);
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

  const noCompData = !ps || ps.transactions === 0;
  const noCompLabour = noCompData || compLabourCost === 0;

  const labourRatio = cs && cs.netSales > 0 ? (labourCost / cs.netSales) * 100 : 0;
  const compLabourRatio = ps && ps.netSales > 0 ? (compLabourCost / ps.netSales) * 100 : 0;

  // Real Profit Margin: Avg margin minus labour ratio
  // avgMargin is the inventory cost margin (what's left after COGS)
  // realMargin = avgMargin - labourRatio (what's left after COGS + labour)
  const realMargin = overallMargin - labourRatio;
  const compRealMargin = overallMargin - compLabourRatio;

  // Weighted margin by sales mix — category-level (most accurate)
  // Uses each category's individual margin from inventory_margins, weighted by
  // how much that category sold this period in actual transactions.
  const computeWeightedMargin = (catSales: CategorySalesTotal[], margins: MarginRow[]) => {
    const marginMap = new Map<string, number>();
    for (const m of margins) {
      if (m.scope_type === "category") marginMap.set(m.scope, m.margin_pct);
    }
    let weightedSum = 0;
    let totalSales = 0;
    for (const cs of catSales) {
      // Use per-category margin if available, else fall back to overall
      const margin = marginMap.get(cs.category) ?? overallMargin;
      weightedSum += cs.net_sales * margin;
      totalSales += cs.net_sales;
    }
    return totalSales > 0 ? weightedSum / totalSales : overallMargin;
  };

  const effectiveMargin = computeWeightedMargin(catSalesTotals, marginData);
  const compEffectiveMargin = computeWeightedMargin(compCatSalesTotals, marginData);

  // Real Profit $ = Net Sales × (Effective Margin / 100) - Labour Cost
  // i.e. gross profit from product markup minus labour
  const realProfitDollar = (cs?.netSales ?? 0) * (effectiveMargin / 100) - labourCost;
  const compRealProfitDollar = (ps?.netSales ?? 0) * (compEffectiveMargin / 100) - compLabourCost;

  const catAgg = aggregateCategoryStats(categoryData);
  const compCatAgg = aggregateCategoryStats(compCategoryData);
  const noCompCat = compCatAgg.cafeNetSales === 0 && compCatAgg.retailNetSales === 0;

  // Cafe/Retail avg sale
  const cafeAvgSale = catAgg.cafeTransactions > 0 ? catAgg.cafeNetSales / catAgg.cafeTransactions : 0;
  const retailAvgSale = catAgg.retailTransactions > 0 ? catAgg.retailNetSales / catAgg.retailTransactions : 0;
  const compCafeAvgSale = compCatAgg.cafeTransactions > 0 ? compCatAgg.cafeNetSales / compCatAgg.cafeTransactions : 0;
  const compRetailAvgSale = compCatAgg.retailTransactions > 0 ? compCatAgg.retailNetSales / compCatAgg.retailTransactions : 0;

  // Cafe/Retail labour ratio
  const cafeLabourRatio = catAgg.cafeNetSales > 0 ? (labourBySide.cafe / catAgg.cafeNetSales) * 100 : 0;
  const retailLabourRatio = catAgg.retailNetSales > 0 ? (labourBySide.retail / catAgg.retailNetSales) * 100 : 0;
  const compCafeLabourRatio = compCatAgg.cafeNetSales > 0 ? (compLabourBySide.cafe / compCatAgg.cafeNetSales) * 100 : 0;
  const compRetailLabourRatio = compCatAgg.retailNetSales > 0 ? (compLabourBySide.retail / compCatAgg.retailNetSales) * 100 : 0;
  const categoryMargins = marginData.filter(m => m.scope_type === "category");

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="space-y-8 relative min-h-[80vh]"
    >
      {loading ? (
        <div className="absolute inset-0 flex items-center justify-center z-40 bg-background">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <div className="w-8 h-8 border-2 border-olive/30 border-t-olive rounded-full animate-spin" />
            <span className="text-sm font-medium">Loading data...</span>
          </div>
        </div>
      ) : (
        <>
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

          {/* ═══ Section 1: Sales & Performance KPIs ═══ */}
          <section>
            {period === "today" && hourlyData.length > 0 && (
              <div className="mb-6">
                <HourlyChart
                  data={hourlyData}
                  comparisonData={compHourlyData}
                  title="Transactions per hour"
                />
              </div>
            )}

            {/* Row 1: 4 cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <KpiCard
                label="Net Sales"
                value={cs?.netSales ?? 0}
                formatter={(n) => formatCurrency(n)}
                change={noCompData ? null : calcChange(cs?.netSales ?? 0, ps?.netSales ?? 0)}
                noCompData={noCompData}
                subtitle={`Gross: ${formatCurrency(cs?.grossSales ?? 0)}`}
                delay={0}
              />
              <KpiCard
                label="Cafe Net Sales"
                value={catAgg.cafeNetSales}
                formatter={(n) => formatCurrency(n)}
                change={noCompCat ? null : calcChange(catAgg.cafeNetSales, compCatAgg.cafeNetSales)}
                noCompData={noCompCat}
                delay={1}
              />
              <KpiCard
                label="Retail Net Sales"
                value={catAgg.retailNetSales}
                formatter={(n) => formatCurrency(n)}
                change={noCompCat ? null : calcChange(catAgg.retailNetSales, compCatAgg.retailNetSales)}
                noCompData={noCompCat}
                delay={2}
              />
              <KpiCard
                label="Transactions"
                value={cs?.transactions ?? 0}
                formatter={(n) => formatNumber(n)}
                change={noCompData ? null : calcChange(cs?.transactions ?? 0, ps?.transactions ?? 0)}
                noCompData={noCompData}
                subtitle={`Cafe: ${formatNumber(catAgg.cafeTransactions)} · Retail: ${formatNumber(catAgg.retailTransactions)}`}
                delay={3}
              />
            </div>

            {/* Row 2: 4 cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
              <KpiCard
                label="Customers"
                value={cs?.totalCustomers ?? 0}
                formatter={(n) => formatNumber(n)}
                change={noCompData ? null : calcChange(cs?.totalCustomers ?? 0, ps?.totalCustomers ?? 0)}
                noCompData={noCompData}
                subtitle="Members + non-members"
                delay={4}
              />
              <KpiCard
                label="Average Sale"
                value={cs?.avgSale ?? 0}
                formatter={(n) => formatCurrency(n)}
                change={noCompData ? null : calcChange(cs?.avgSale ?? 0, ps?.avgSale ?? 0)}
                noCompData={noCompData}
                subtitle={`Cafe: ${formatCurrency(cafeAvgSale)} · Retail: ${formatCurrency(retailAvgSale)}`}
                delay={5}
              />
              <KpiCard
                label="Labour Cost"
                value={labourCost}
                formatter={(n) => formatCurrency(n)}
                change={noCompLabour ? null : calcChange(labourCost, compLabourCost)}
                noCompData={noCompLabour}
                invertColor
                subtitle={`Cafe: ${formatCurrency(labourBySide.cafe)} · Retail: ${formatCurrency(labourBySide.retail)}`}
                delay={6}
              />
              <KpiCard
                label="Labour vs Sales %"
                value={labourRatio}
                formatter={(n) => formatPercent(n)}
                change={noCompLabour ? null : calcChange(labourRatio, compLabourRatio)}
                noCompData={noCompLabour}
                invertColor
                subtitle={`Cafe: ${formatPercent(cafeLabourRatio)} · Retail: ${formatPercent(retailLabourRatio)}`}
                delay={7}
              />
            </div>

            {/* Row 3: 3 cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
              <KpiCard
                label="Avg Profit Margin"
                value={effectiveMargin}
                formatter={(n) => formatPercent(n)}
                change={noCompCat ? null : calcChange(effectiveMargin, compEffectiveMargin)}
                noCompData={noCompCat}
                subtitle={`Cafe: ${formatPercent(cafeMargin)} · Retail: ${formatPercent(retailMargin)}`}
                tooltip="Weighted by Cafe/Retail sales mix this period. Cafe items carry ~70% margin, Retail ~41%."
                delay={8}
              />
              <KpiCard
                label="Real Profit Margin"
                value={realMargin}
                formatter={(n) => formatPercent(n)}
                change={noCompLabour ? null : calcChange(realMargin, compRealMargin)}
                noCompData={noCompLabour}
                subtitle={`Margin ${formatPercent(effectiveMargin)} − Labour ${formatPercent(labourRatio)}`}
                tooltip="Profit margin after subtracting labour costs. Formula: Avg Margin − (Labour ÷ Net Sales × 100)."
                accent
                delay={9}
              />
              <KpiCard
                label="Real Profit"
                value={realProfitDollar}
                formatter={(n) => formatCurrency(n)}
                change={noCompLabour ? null : calcChange(realProfitDollar, compRealProfitDollar)}
                noCompData={noCompLabour}
                subtitle="After COGS + labour"
                tooltip="Take-home profit: Net Sales × Avg Margin% − Labour Cost. Excludes rent, utilities, and overheads."
                accent
                delay={10}
              />
            </div>
          </section>

          {/* ═══ Section 2: Time-Series Chart ═══ */}
          <section>
            <MetricTimeSeriesChart
              dailyStats={dailyRows}
              compDailyStats={compDailyRows}
              categoryData={categoryData}
              compCategoryData={compCategoryData}
              dailyLabour={dailyLabour}
              compDailyLabour={compDailyLabour}
              historicalStats={historicalStats}
              historicalCategoryData={historicalCategoryData}
              historicalLabour={historicalLabour}
              effectiveMargin={effectiveMargin}
              categoryDetailData={categoryDetailData}
            />
          </section>

          {/* ═══ Section 3: Category Margins Visualization ═══ */}
          {categoryMargins.length > 0 && (
            <section>
              <CategoryMarginChart data={categoryMargins} />
            </section>
          )}
        </>
      )}
    </motion.div>
  );
}
