import React from "react";

interface Props {
  onClick: () => void;
  disabled?: boolean;
}

export function CheckoutButton({ onClick, disabled }: Props) {
  return (
    <button
      data-testid="checkout-btn"
      onClick={onClick}
      disabled={disabled}
      className="btn btn-primary"
    >
      {disabled ? "Processing…" : "Place Order"}
    </button>
  );
}
