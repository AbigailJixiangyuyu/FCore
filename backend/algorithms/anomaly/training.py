"""Offline SLADE training and deterministic warmup with the final parameters."""

from dataclasses import asdict

import torch

from .events import Event, chronological_batches
from .runtime import cuda_device
from .slade import Slade, SladeConfig
from .state import MemoryState


def train(events: tuple[Event, ...], config: SladeConfig, progress=None):
    if not events:
        raise ValueError("The training history contains no interactions.")
    device = cuda_device()
    torch.manual_seed(config.seed)
    torch.cuda.manual_seed_all(config.seed)
    model = Slade(config).to(device)
    accounts = sorted({account for event in events for account in (event.u, event.v)})
    optimizer = torch.optim.Adam(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.ExponentialLR(optimizer, gamma=config.lr_decay)
    losses = []
    for epoch in range(config.epochs):
        model.train()
        state = MemoryState.empty(accounts, config.memory_dim, device)
        epoch_losses = []
        previous_batch = ()
        for batch in chronological_batches(events, config.batch_size):
            optimizer.zero_grad()
            loss = model.training_loss(state, batch, previous_batch)
            if not torch.isfinite(loss):
                raise ValueError("The SLADE training loss is not finite.")
            loss.backward()
            optimizer.step()
            state.detach()
            epoch_losses.append(float(loss.detach()))
            previous_batch = batch
        losses.append(sum(epoch_losses) / len(epoch_losses))
        scheduler.step()
        if progress:
            progress(epoch + 1, losses[-1])
    model.eval()
    bootstrap = MemoryState.empty(accounts, config.memory_dim, device)
    model.replay(bootstrap, events)
    return model, bootstrap, {"config": asdict(config), "epoch_losses": losses}
