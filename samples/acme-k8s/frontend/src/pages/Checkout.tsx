import React, { useState } from "react";
import { CheckoutButton } from "../components/CheckoutButton";
import { placeOrder } from "../api/client";

export function CheckoutPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCheckout = async () => {
    setLoading(true);
    setError(null);
    try {
      await placeOrder({ items: [] }); // stub
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Checkout</h1>
      {error && <p className="error">{error}</p>}
      <CheckoutButton onClick={handleCheckout} disabled={loading} />
    </div>
  );
}
