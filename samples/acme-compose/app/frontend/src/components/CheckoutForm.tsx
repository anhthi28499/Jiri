import React, { useState } from "react";
import { placeOrder } from "../api/client";

export function CheckoutForm() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await placeOrder({ items: [] });
    } catch (err: any) {
      setError(err.message ?? "Unknown error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Complete your order</h2>
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={submitting} data-testid="submit-order">
        {submitting ? "Placing order…" : "Place Order"}
      </button>
    </form>
  );
}
