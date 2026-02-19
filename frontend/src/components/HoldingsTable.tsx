import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { portfoliosApi } from "../api/portfolios";
import type { Holding } from "../types";

interface HoldingsTableProps {
  holdings: Holding[];
  portfolioId: number;
  priceMap?: Record<string, number>;
}

export function HoldingsTable({ holdings, portfolioId, priceMap = {} }: HoldingsTableProps) {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editAmount, setEditAmount] = useState("");
  const [editPrice, setEditPrice] = useState("");

  const updateMutation = useMutation({
    mutationFn: ({ holdingId, data }: { holdingId: number; data: { amount?: number; avg_buy_price?: number } }) =>
      portfoliosApi.updateHolding(portfolioId, holdingId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["portfolios"] });
      setEditingId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (holdingId: number) => portfoliosApi.deleteHolding(portfolioId, holdingId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["portfolios"] }),
  });

  const startEdit = (h: Holding) => {
    setEditingId(h.id);
    setEditAmount(String(h.amount ?? 0));
    setEditPrice(String(h.avg_buy_price ?? 0));
  };

  const saveEdit = (holdingId: number) => {
    updateMutation.mutate({
      holdingId,
      data: { amount: Number(editAmount), avg_buy_price: Number(editPrice) },
    });
  };

  if (holdings.length === 0) {
    return (
      <p className="text-sm text-[var(--color-text-muted)]">
        No holdings yet.
      </p>
    );
  }

  const hasLivePrices = holdings.some((h) => priceMap[h.symbol] != null);

  let totalCost = 0;
  let totalValue = 0;
  for (const h of holdings) {
    const amt = h.amount ?? 0;
    const avg = h.avg_buy_price ?? 0;
    const cost = amt * avg;
    const price = priceMap[h.symbol];
    const value = price != null ? amt * price : cost;
    totalCost += cost;
    totalValue += value;
  }
  const totalPnl = totalValue - totalCost;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
            <th className="pb-2">Symbol</th>
            <th className="pb-2">Amount</th>
            <th className="pb-2">Avg Buy Price</th>
            {hasLivePrices && <th className="pb-2">Current Price</th>}
            <th className="pb-2">Cost Basis</th>
            {hasLivePrices && <th className="pb-2">Current Value</th>}
            {hasLivePrices && <th className="pb-2">P&L</th>}
            {hasLivePrices && <th className="pb-2">P&L %</th>}
            <th className="pb-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const amt = h.amount ?? 0;
            const avg = h.avg_buy_price ?? 0;
            const cost = amt * avg;
            const price = priceMap[h.symbol];
            const value = price != null ? amt * price : null;
            const pnl = value != null ? value - cost : null;
            const pnlPct = cost > 0 && pnl != null ? (pnl / cost) * 100 : null;
            const isEditing = editingId === h.id;

            return (
              <tr
                key={h.id}
                className="border-b border-[var(--color-border)]"
              >
                <td className="py-2 font-medium">{h.symbol}</td>
                <td className="py-2">
                  {isEditing ? (
                    <input
                      type="number"
                      value={editAmount}
                      onChange={(e) => setEditAmount(e.target.value)}
                      className="w-24 rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs"
                      step="any"
                    />
                  ) : (
                    amt.toFixed(6)
                  )}
                </td>
                <td className="py-2">
                  {isEditing ? (
                    <input
                      type="number"
                      value={editPrice}
                      onChange={(e) => setEditPrice(e.target.value)}
                      className="w-24 rounded border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 text-xs"
                      step="any"
                    />
                  ) : (
                    `$${avg.toLocaleString()}`
                  )}
                </td>
                {hasLivePrices && (
                  <td className="py-2">
                    {price != null ? `$${price.toLocaleString()}` : "\u2014"}
                  </td>
                )}
                <td className="py-2">${cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                {hasLivePrices && (
                  <td className="py-2">
                    {value != null ? `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "\u2014"}
                  </td>
                )}
                {hasLivePrices && (
                  <td className={`py-2 font-mono ${pnl != null && pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {pnl != null ? `${pnl >= 0 ? "+" : ""}$${pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "\u2014"}
                  </td>
                )}
                {hasLivePrices && (
                  <td className={`py-2 font-mono ${pnlPct != null && pnlPct >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {pnlPct != null ? `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%` : "\u2014"}
                  </td>
                )}
                <td className="py-2 text-right">
                  {isEditing ? (
                    <span className="flex justify-end gap-1">
                      <button
                        onClick={() => saveEdit(h.id)}
                        disabled={updateMutation.isPending}
                        className="rounded bg-green-500/20 px-2 py-1 text-xs text-green-400 hover:bg-green-500/30"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="rounded bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text-muted)]"
                      >
                        Cancel
                      </button>
                    </span>
                  ) : (
                    <span className="flex justify-end gap-1">
                      <button
                        onClick={() => startEdit(h)}
                        className="rounded bg-[var(--color-bg)] px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(h.id)}
                        disabled={deleteMutation.isPending}
                        className="rounded bg-red-500/10 px-2 py-1 text-xs text-red-400 hover:bg-red-500/20"
                      >
                        Delete
                      </button>
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
          {/* Total row */}
          <tr className="font-medium">
            <td className="py-2">Total</td>
            <td className="py-2"></td>
            <td className="py-2"></td>
            {hasLivePrices && <td className="py-2"></td>}
            <td className="py-2">${totalCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            {hasLivePrices && (
              <td className="py-2">${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            )}
            {hasLivePrices && (
              <td className={`py-2 font-mono ${totalPnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                {totalPnl >= 0 ? "+" : ""}${totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
            )}
            {hasLivePrices && <td className="py-2"></td>}
            <td className="py-2"></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
