import { Router } from "express";
import { verifyJwt } from "../middleware/auth";

export const ordersRouter = Router();

ordersRouter.use(verifyJwt);

ordersRouter.post("/", async (req, res) => {
  const { items } = req.body;
  if (!Array.isArray(items)) {
    return res.status(400).json({ error: "items must be an array" });
  }
  // TODO: persist order
  res.status(201).json({ id: "order-stub", items, status: "pending" });
});

ordersRouter.get("/:id", async (req, res) => {
  res.json({ id: req.params.id, status: "pending" });
});
