# Frontend Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the frontend with shadcn/ui, React Router, warm dark fintech palette, and KPI summary + tabbed analysis layout.

**Architecture:** Replace custom glass-card components with shadcn/ui primitives. Add React Router for URL-based navigation. Reorganize analysis view from scrolling sections into KPI row + 5 tabbed sections. Keep existing data layer (AnalysisContext, hooks, api.js) intact.

**Tech Stack:** React 19, shadcn/ui (Radix), React Router v6, Tailwind CSS v4, Lightweight Charts v5, Framer Motion v12, Lucide React icons, Inter + Fira Code fonts.

**Spec:** `docs/superpowers/specs/2026-04-03-frontend-overhaul-design.md`

---

## File Structure (Final State)

```
frontend/src/
├── main.jsx                          # Add BrowserRouter wrapper
├── App.jsx                           # Replace with Routes definition
├── index.css                         # New design tokens, remove glass-card classes
├── lib/
│   └── utils.js                      # cn() helper (NEW)
├── components/
│   ├── ui/                           # shadcn primitives (NEW, ~11 files)
│   │   ├── card.jsx
│   │   ├── tabs.jsx
│   │   ├── table.jsx
│   │   ├── badge.jsx
│   │   ├── button.jsx
│   │   ├── dialog.jsx
│   │   ├── dropdown-menu.jsx
│   │   ├── input.jsx
│   │   ├── select.jsx
│   │   ├── tooltip.jsx
│   │   └── skeleton.jsx
│   ├── layout/                       # Layout components (NEW)
│   │   ├── AppLayout.jsx
│   │   ├── Header.jsx
│   │   └── Sidebar.jsx
│   ├── analysis/                     # Analysis view components (NEW)
│   │   ├── AnalysisView.jsx
│   │   ├── AnalysisTabs.jsx
│   │   ├── KpiRow.jsx
│   │   ├── KpiCard.jsx
│   │   ├── OverviewTab.jsx
│   │   ├── ThesisRiskTab.jsx
│   │   ├── TechnicalsTab.jsx
│   │   ├── SentimentTab.jsx
│   │   └── CouncilTab.jsx
│   ├── panels/                       # Migrated content panels (MOVED + RESTYLED)
│   │   ├── CompanyOverview.jsx
│   │   ├── ThesisPanel.jsx
│   │   ├── NarrativePanel.jsx
│   │   ├── RiskDiffPanel.jsx
│   │   ├── EarningsReviewPanel.jsx
│   │   ├── EarningsPanel.jsx
│   │   ├── PriceChart.jsx
│   │   ├── TechnicalsOptionsSection.jsx
│   │   ├── SentimentPanel.jsx        # NEW — extracted from Dashboard inline rendering
│   │   ├── NewsFeed.jsx
│   │   ├── OptionsFlow.jsx
│   │   ├── LeadershipPanel.jsx
│   │   ├── CouncilPanel.jsx
│   │   ├── Icons.jsx                 # Keep existing, supplement with Lucide
│   │   └── MetaFooter.jsx
│   └── views/                        # Full-page views (MOVED + RESTYLED)
│       ├── MacroPage.jsx
│       ├── HistoryView.jsx
│       ├── WatchlistView.jsx
│       ├── PortfolioView.jsx
│       ├── SchedulesView.jsx
│       ├── AlertsView.jsx
│       ├── InflectionView.jsx
│       ├── InflectionChart.jsx
│       ├── InflectionHeatmap.jsx
│       └── InflectionFeed.jsx
├── context/
│   └── AnalysisContext.jsx           # Unchanged
├── hooks/
│   ├── useAnalysis.js                # Minor: add navigate() call
│   ├── useSSE.js                     # Unchanged
│   └── useHistory.js                 # Unchanged
├── utils/
│   └── api.js                        # Unchanged
└── assets/
```

**Files to delete after migration:**
- `src/components/Dashboard.jsx` (replaced by AppLayout + AnalysisView)
- `src/components/Sidebar.jsx` (replaced by layout/Sidebar.jsx)
- `src/components/SearchBar.jsx` (merged into layout/Header.jsx)
- `src/components/SectionNav.jsx` (replaced by shadcn Tabs)
- `src/components/ThesisCard.jsx` (replaced by KpiRow)
- `src/components/AnalysisSection.jsx` (replaced by direct Card usage)

---

## Task 1: Install Dependencies and Set Up shadcn/ui Foundation

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/lib/utils.js`
- Create: `frontend/components.json` (shadcn config)

- [ ] **Step 1: Install new dependencies**

```bash
cd frontend
npm install react-router-dom@6 lucide-react class-variance-authority clsx tailwind-merge
```

- [ ] **Step 2: Create the cn() utility**

Create `frontend/src/lib/utils.js`:

```javascript
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Create shadcn components.json config**

Create `frontend/components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": false,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "zinc",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui"
  }
}
```

- [ ] **Step 4: Add path aliases to vite.config.js**

Replace `frontend/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
```

- [ ] **Step 5: Create directory structure**

```bash
mkdir -p frontend/src/components/ui
mkdir -p frontend/src/components/layout
mkdir -p frontend/src/components/analysis
mkdir -p frontend/src/components/panels
mkdir -p frontend/src/components/views
mkdir -p frontend/src/lib
```

- [ ] **Step 6: Verify the build still works**

```bash
cd frontend && npm run build
```

Expected: Build succeeds (no functional changes yet).

- [ ] **Step 7: Commit**

```bash
git add -A frontend/
git commit -m "chore: install shadcn/ui dependencies and set up foundation"
```

---

## Task 2: Create shadcn UI Primitives

**Files:**
- Create: `frontend/src/components/ui/card.jsx`
- Create: `frontend/src/components/ui/button.jsx`
- Create: `frontend/src/components/ui/badge.jsx`
- Create: `frontend/src/components/ui/tabs.jsx`
- Create: `frontend/src/components/ui/input.jsx`
- Create: `frontend/src/components/ui/table.jsx`
- Create: `frontend/src/components/ui/dialog.jsx`
- Create: `frontend/src/components/ui/tooltip.jsx`
- Create: `frontend/src/components/ui/skeleton.jsx`
- Create: `frontend/src/components/ui/select.jsx`
- Create: `frontend/src/components/ui/dropdown-menu.jsx`

These are shadcn/ui components adapted for our dark theme with JSX (not TSX). Each component uses Radix primitives + our cn() utility + Tailwind classes.

- [ ] **Step 1: Install Radix primitives**

```bash
cd frontend
npm install @radix-ui/react-slot @radix-ui/react-tabs @radix-ui/react-dialog @radix-ui/react-tooltip @radix-ui/react-select @radix-ui/react-dropdown-menu @radix-ui/react-separator
```

- [ ] **Step 2: Create Card component**

Create `frontend/src/components/ui/card.jsx`:

```jsx
import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-lg border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)]",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-5", className)}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-[var(--muted-foreground)]", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-5 pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-5 pt-0", className)}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
```

- [ ] **Step 3: Create Button component**

Create `frontend/src/components/ui/button.jsx`:

```jsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ring)] disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-[var(--primary)]/90",
        destructive: "bg-[var(--destructive)] text-white hover:bg-[var(--destructive)]/90",
        outline: "border border-[var(--border)] bg-transparent hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
        secondary: "bg-[var(--secondary)] text-[var(--secondary-foreground)] hover:bg-[var(--secondary)]/80",
        ghost: "hover:bg-[var(--secondary)] hover:text-[var(--secondary-foreground)]",
        link: "text-[var(--primary)] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

- [ ] **Step 4: Create Badge component**

Create `frontend/src/components/ui/badge.jsx`:

```jsx
import * as React from "react"
import { cva } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-[var(--primary)] text-[var(--primary-foreground)]",
        secondary: "border-transparent bg-[var(--secondary)] text-[var(--secondary-foreground)]",
        destructive: "border-transparent bg-[var(--destructive)] text-white",
        outline: "text-[var(--card-foreground)]",
        success: "border-transparent bg-[rgba(23,201,100,0.15)] text-[#17c964]",
        warning: "border-transparent bg-[rgba(245,165,36,0.15)] text-[#f5a524]",
        danger: "border-transparent bg-[rgba(243,18,96,0.15)] text-[#f31260]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const Badge = React.forwardRef(({ className, variant, ...props }, ref) => (
  <div ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />
))
Badge.displayName = "Badge"

export { Badge, badgeVariants }
```

- [ ] **Step 5: Create Tabs component**

Create `frontend/src/components/ui/tabs.jsx`:

```jsx
import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"
import { cn } from "@/lib/utils"

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "inline-flex h-10 items-center gap-1 rounded-lg bg-[var(--secondary)] p-1",
      className
    )}
    {...props}
  />
))
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium text-[var(--muted-foreground)] ring-offset-[var(--background)] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-[var(--card)] data-[state=active]:text-[var(--card-foreground)] data-[state=active]:shadow cursor-pointer",
      className
    )}
    {...props}
  />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-4 ring-offset-[var(--background)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2",
      className
    )}
    {...props}
  />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
```

- [ ] **Step 6: Create Input component**

Create `frontend/src/components/ui/input.jsx`:

```jsx
import * as React from "react"
import { cn } from "@/lib/utils"

const Input = React.forwardRef(({ className, type, ...props }, ref) => (
  <input
    type={type}
    className={cn(
      "flex h-9 w-full rounded-md border border-[var(--input)] bg-transparent px-3 py-1 text-sm text-[var(--card-foreground)] shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[var(--muted-foreground)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50",
      className
    )}
    ref={ref}
    {...props}
  />
))
Input.displayName = "Input"

export { Input }
```

- [ ] **Step 7: Create Table component**

Create `frontend/src/components/ui/table.jsx`:

```jsx
import * as React from "react"
import { cn } from "@/lib/utils"

const Table = React.forwardRef(({ className, ...props }, ref) => (
  <div className="relative w-full overflow-auto">
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
))
Table.displayName = "Table"

const TableHeader = React.forwardRef(({ className, ...props }, ref) => (
  <thead ref={ref} className={cn("[&_tr]:border-b", className)} {...props} />
))
TableHeader.displayName = "TableHeader"

const TableBody = React.forwardRef(({ className, ...props }, ref) => (
  <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />
))
TableBody.displayName = "TableBody"

const TableFooter = React.forwardRef(({ className, ...props }, ref) => (
  <tfoot
    ref={ref}
    className={cn("border-t bg-[var(--muted)]/50 font-medium [&>tr]:last:border-b-0", className)}
    {...props}
  />
))
TableFooter.displayName = "TableFooter"

const TableRow = React.forwardRef(({ className, ...props }, ref) => (
  <tr
    ref={ref}
    className={cn(
      "border-b border-[var(--border)] transition-colors hover:bg-[var(--muted)]/50 data-[state=selected]:bg-[var(--muted)]",
      className
    )}
    {...props}
  />
))
TableRow.displayName = "TableRow"

const TableHead = React.forwardRef(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "h-10 px-3 text-left align-middle font-medium text-[var(--muted-foreground)] [&:has([role=checkbox])]:pr-0",
      className
    )}
    {...props}
  />
))
TableHead.displayName = "TableHead"

const TableCell = React.forwardRef(({ className, ...props }, ref) => (
  <td
    ref={ref}
    className={cn("px-3 py-3 align-middle [&:has([role=checkbox])]:pr-0", className)}
    {...props}
  />
))
TableCell.displayName = "TableCell"

const TableCaption = React.forwardRef(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-[var(--muted-foreground)]", className)}
    {...props}
  />
))
TableCaption.displayName = "TableCaption"

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption }
```

- [ ] **Step 8: Create Dialog component**

Create `frontend/src/components/ui/dialog.jsx`:

```jsx
import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const Dialog = DialogPrimitive.Root
const DialogTrigger = DialogPrimitive.Trigger
const DialogPortal = DialogPrimitive.Portal
const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName

const DialogContent = React.forwardRef(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-[var(--border)] bg-[var(--card)] p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        className
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-[var(--background)] transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-[var(--secondary)]">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitive.Content.displayName

const DialogHeader = ({ className, ...props }) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({ className, ...props }) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props} />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
DialogTitle.displayName = DialogPrimitive.Title.displayName

const DialogDescription = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-[var(--muted-foreground)]", className)}
    {...props}
  />
))
DialogDescription.displayName = DialogPrimitive.Description.displayName

export {
  Dialog, DialogPortal, DialogOverlay, DialogClose, DialogTrigger,
  DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription,
}
```

- [ ] **Step 9: Create Tooltip component**

Create `frontend/src/components/ui/tooltip.jsx`:

```jsx
import * as React from "react"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import { cn } from "@/lib/utils"

const TooltipProvider = TooltipPrimitive.Provider
const Tooltip = TooltipPrimitive.Root
const TooltipTrigger = TooltipPrimitive.Trigger

const TooltipContent = React.forwardRef(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-md bg-[var(--popover)] px-3 py-1.5 text-xs text-[var(--popover-foreground)] border border-[var(--border)] animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
      className
    )}
    {...props}
  />
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
```

- [ ] **Step 10: Create Skeleton component**

Create `frontend/src/components/ui/skeleton.jsx`:

```jsx
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-[var(--muted)]", className)}
      {...props}
    />
  )
}

export { Skeleton }
```

- [ ] **Step 11: Create Select component**

Create `frontend/src/components/ui/select.jsx`:

```jsx
import * as React from "react"
import * as SelectPrimitive from "@radix-ui/react-select"
import { Check, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"

const Select = SelectPrimitive.Root
const SelectGroup = SelectPrimitive.Group
const SelectValue = SelectPrimitive.Value

const SelectTrigger = React.forwardRef(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex h-9 w-full items-center justify-between whitespace-nowrap rounded-md border border-[var(--input)] bg-transparent px-3 py-2 text-sm text-[var(--card-foreground)] shadow-sm ring-offset-[var(--background)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1 cursor-pointer",
      className
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon asChild>
      <ChevronDown className="h-4 w-4 opacity-50" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
))
SelectTrigger.displayName = SelectPrimitive.Trigger.displayName

const SelectContent = React.forwardRef(({ className, children, position = "popper", ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      className={cn(
        "relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border border-[var(--border)] bg-[var(--popover)] text-[var(--popover-foreground)] shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        position === "popper" && "data-[side=bottom]:translate-y-1 data-[side=left]:-translate-x-1 data-[side=right]:translate-x-1 data-[side=top]:-translate-y-1",
        className
      )}
      position={position}
      {...props}
    >
      <SelectPrimitive.Viewport
        className={cn(
          "p-1",
          position === "popper" && "h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]"
        )}
      >
        {children}
      </SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
))
SelectContent.displayName = SelectPrimitive.Content.displayName

const SelectItem = React.forwardRef(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-2 pr-8 text-sm outline-none focus:bg-[var(--secondary)] focus:text-[var(--secondary-foreground)] data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      className
    )}
    {...props}
  >
    <span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="h-4 w-4" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
))
SelectItem.displayName = SelectPrimitive.Item.displayName

const SelectSeparator = React.forwardRef(({ className, ...props }, ref) => (
  <SelectPrimitive.Separator
    ref={ref}
    className={cn("-mx-1 my-1 h-px bg-[var(--muted)]", className)}
    {...props}
  />
))
SelectSeparator.displayName = SelectPrimitive.Separator.displayName

export { Select, SelectGroup, SelectValue, SelectTrigger, SelectContent, SelectItem, SelectSeparator }
```

- [ ] **Step 12: Create DropdownMenu component**

Create `frontend/src/components/ui/dropdown-menu.jsx`:

```jsx
import * as React from "react"
import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu"
import { Check, ChevronRight, Circle } from "lucide-react"
import { cn } from "@/lib/utils"

const DropdownMenu = DropdownMenuPrimitive.Root
const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger
const DropdownMenuGroup = DropdownMenuPrimitive.Group
const DropdownMenuSub = DropdownMenuPrimitive.Sub

const DropdownMenuContent = React.forwardRef(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-md border border-[var(--border)] bg-[var(--popover)] p-1 text-[var(--popover-foreground)] shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
))
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName

const DropdownMenuItem = React.forwardRef(({ className, inset, ...props }, ref) => (
  <DropdownMenuPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-[var(--secondary)] focus:text-[var(--secondary-foreground)] data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
      inset && "pl-8",
      className
    )}
    {...props}
  />
))
DropdownMenuItem.displayName = DropdownMenuPrimitive.Item.displayName

const DropdownMenuSeparator = React.forwardRef(({ className, ...props }, ref) => (
  <DropdownMenuPrimitive.Separator
    ref={ref}
    className={cn("-mx-1 my-1 h-px bg-[var(--muted)]", className)}
    {...props}
  />
))
DropdownMenuSeparator.displayName = DropdownMenuPrimitive.Separator.displayName

const DropdownMenuLabel = React.forwardRef(({ className, inset, ...props }, ref) => (
  <DropdownMenuPrimitive.Label
    ref={ref}
    className={cn("px-2 py-1.5 text-sm font-semibold", inset && "pl-8", className)}
    {...props}
  />
))
DropdownMenuLabel.displayName = DropdownMenuPrimitive.Label.displayName

export {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
  DropdownMenuGroup, DropdownMenuSub,
}
```

- [ ] **Step 13: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 14: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat: add shadcn/ui component primitives for dark theme"
```

---

## Task 3: Replace Design Tokens in index.css

**Files:**
- Modify: `frontend/src/index.css`

Replace the entire design token system with the warm dark fintech palette. Keep keyframe animations. Remove glass-card utilities and old sidebar styles.

- [ ] **Step 1: Replace index.css**

Replace `frontend/src/index.css` with the new design system. The file has three sections: (A) Tailwind imports + Google Fonts, (B) CSS custom properties on `:root`, (C) keyframe animations, (D) global utility styles.

```css
@import "tailwindcss";
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700&display=swap');

/* ============================================
   DESIGN TOKENS — Warm Dark Fintech
   ============================================ */

:root {
  /* Core surfaces */
  --background: #0a0a0a;
  --foreground: rgba(255, 255, 255, 0.92);
  --card: #141414;
  --card-foreground: rgba(255, 255, 255, 0.92);
  --card-hover: #1a1a1a;
  --popover: #181818;
  --popover-foreground: rgba(255, 255, 255, 0.92);

  /* Primary accent — warm amber */
  --primary: #e8860c;
  --primary-foreground: #000000;

  /* Secondary */
  --secondary: #1f1f1f;
  --secondary-foreground: rgba(255, 255, 255, 0.8);

  /* Muted */
  --muted: #1a1a1a;
  --muted-foreground: rgba(255, 255, 255, 0.4);

  /* Accent (alias of primary) */
  --accent: #e8860c;
  --accent-foreground: #000000;

  /* Destructive */
  --destructive: #f31260;

  /* Borders & inputs */
  --border: rgba(255, 255, 255, 0.06);
  --border-hover: rgba(255, 255, 255, 0.12);
  --input: rgba(255, 255, 255, 0.08);
  --ring: #e8860c;

  /* Radius */
  --radius: 8px;

  /* Semantic status colors */
  --success: #17c964;
  --danger: #f31260;
  --warning: #f5a524;
  --info: #338ef7;

  /* Layout surfaces */
  --sidebar-bg: #0d0d0d;
  --header-bg: #0d0d0d;
  --sidebar-active-bg: rgba(232, 134, 12, 0.08);
  --sidebar-active-border: rgba(232, 134, 12, 0.4);

  /* Text hierarchy */
  --text-primary: rgba(255, 255, 255, 0.92);
  --text-secondary: rgba(255, 255, 255, 0.6);
  --text-muted: rgba(255, 255, 255, 0.35);

  /* Sentiment colors */
  --accent-buy: #17c964;
  --accent-sell: #f31260;
  --accent-hold: #f5a524;

  /* Chart series */
  --chart-1: #e8860c;
  --chart-2: #338ef7;
  --chart-3: #17c964;
  --chart-4: #f5a524;
  --chart-5: #a855f7;

  /* SMA colors */
  --sma-9: #ef4444;
  --sma-20: #f59e0b;
  --sma-50: #22c55e;
  --sma-100: #3b82f6;
  --sma-200: #a855f7;

  /* Shadows */
  --shadow-subtle: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-elevated: 0 4px 12px rgba(0, 0, 0, 0.5);

  /* Spacing */
  --sidebar-width: 220px;
  --header-height: 56px;
  --space-card-gap: 16px;
  --space-section-gap: 24px;
  --space-card-padding: 20px;

  /* Typography */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'Fira Code', 'JetBrains Mono', ui-monospace, monospace;
}

/* ============================================
   GLOBAL STYLES
   ============================================ */

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  color-scheme: dark;
}

body {
  font-family: var(--font-sans);
  background-color: var(--background);
  color: var(--foreground);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  overflow: hidden;
}

/* ============================================
   SCROLLBAR
   ============================================ */

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}

* {
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.1) transparent;
}

/* ============================================
   KEYFRAME ANIMATIONS
   ============================================ */

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes slideInUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes scaleIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 4px currentColor; }
  50% { box-shadow: 0 0 12px currentColor; }
}

@keyframes progressShine {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}

/* Animation utilities */
.animate-fade-in { animation: fadeIn 0.3s ease-out forwards; }
.animate-slide-up { animation: slideInUp 0.3s ease-out forwards; }
.animate-scale-in { animation: scaleIn 0.2s ease-out forwards; }
.animate-spin-slow { animation: spin 2s linear infinite; }

/* Skeleton shimmer */
.skeleton {
  background: linear-gradient(90deg, var(--muted) 25%, var(--card-hover) 50%, var(--muted) 75%);
  background-size: 400% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

/* ============================================
   UTILITY CLASSES
   ============================================ */

/* Data value typography */
.font-data {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

/* Badge sentiment colors */
.badge-bullish { background: rgba(23, 201, 100, 0.12); color: #17c964; }
.badge-bearish { background: rgba(243, 18, 96, 0.12); color: #f31260; }
.badge-neutral { background: rgba(245, 165, 36, 0.12); color: #f5a524; }

/* Progress bar */
.progress-bar {
  height: 2px;
  background: linear-gradient(90deg, var(--primary), var(--success));
  position: relative;
  overflow: hidden;
}

.progress-bar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  animation: progressShine 1.5s ease-in-out infinite;
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. The old components will have broken styles (expected — we're replacing them).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: replace design tokens with warm dark fintech palette"
```

---

## Task 4: Build Layout Components (AppLayout, Header, Sidebar)

**Files:**
- Create: `frontend/src/components/layout/AppLayout.jsx`
- Create: `frontend/src/components/layout/Header.jsx`
- Create: `frontend/src/components/layout/Sidebar.jsx`

- [ ] **Step 1: Create Header component**

Create `frontend/src/components/layout/Header.jsx`:

```jsx
import { Search, Bell, Settings, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useAnalysisContext } from '@/context/AnalysisContext'

const AGENT_KEYS = ['market', 'fundamentals', 'technical', 'news', 'sentiment', 'macro', 'options']

const STAGE_LABELS = {
  initializing: 'Starting...',
  running_market: 'Market data',
  running_fundamentals: 'Fundamentals',
  running_technical: 'Technicals',
  running_news: 'News',
  running_sentiment: 'Sentiment',
  running_macro: 'Macro',
  running_options: 'Options',
  running_solution: 'Synthesizing',
  running_thesis: 'Thesis',
  completed: 'Complete',
}

export default function Header({ tickerInput, setTickerInput, onAnalyze, unacknowledgedCount }) {
  const { loading, stage, progress, analysis } = useAnalysisContext()

  return (
    <header
      className="fixed top-0 left-0 right-0 z-40 flex items-center gap-4 px-4 border-b border-[var(--border)]"
      style={{ height: 'var(--header-height)', backgroundColor: 'var(--header-bg)' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 w-[180px] shrink-0">
        <div className="w-8 h-8 rounded-lg bg-[var(--primary)] flex items-center justify-center">
          <span className="text-black font-bold text-sm">MR</span>
        </div>
        <span className="font-semibold text-sm text-[var(--text-primary)]">Market Research</span>
      </div>

      {/* Search bar */}
      <form onSubmit={onAnalyze} className="flex-1 max-w-md mx-auto flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--muted-foreground)]" />
          <Input
            value={tickerInput}
            onChange={(e) => setTickerInput(e.target.value.toUpperCase().slice(0, 5))}
            placeholder="Search ticker..."
            className="pl-9 h-9 bg-[var(--secondary)] border-[var(--border)] font-data"
            disabled={loading}
          />
        </div>
        <Button type="submit" size="sm" disabled={loading || !tickerInput.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Analyze'}
        </Button>
      </form>

      {/* Agent progress dots */}
      {loading && (
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1">
            {AGENT_KEYS.map((key) => {
              const agentResult = analysis?.agent_results?.[key]
              let color = 'rgba(255,255,255,0.15)'
              if (agentResult?.success) color = 'var(--success)'
              else if (agentResult?.success === false) color = 'var(--danger)'
              else if (stage?.includes(key)) color = 'var(--primary)'
              return (
                <div
                  key={key}
                  className="w-1.5 h-1.5 rounded-full transition-colors duration-300"
                  style={{ backgroundColor: color }}
                />
              )
            })}
          </div>
          <span className="text-xs text-[var(--muted-foreground)]">
            {STAGE_LABELS[stage] || stage}
          </span>
        </div>
      )}

      {/* Right actions */}
      <div className="flex items-center gap-1 shrink-0">
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-4 w-4" />
          {unacknowledgedCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-[var(--danger)] text-[10px] font-bold flex items-center justify-center text-white">
              {unacknowledgedCount > 9 ? '9+' : unacknowledgedCount}
            </span>
          )}
        </Button>
        <Button variant="ghost" size="icon">
          <Settings className="h-4 w-4" />
        </Button>
      </div>

      {/* Progress bar */}
      {loading && progress > 0 && (
        <div
          className="absolute bottom-0 left-0 h-[2px] transition-all duration-300"
          style={{
            width: `${progress}%`,
            background: `linear-gradient(90deg, var(--primary), var(--success))`,
          }}
        />
      )}
    </header>
  )
}
```

- [ ] **Step 2: Create Sidebar component**

Create `frontend/src/components/layout/Sidebar.jsx`:

```jsx
import { NavLink } from 'react-router-dom'
import {
  Activity, BarChart3, Bell, Briefcase, Calendar, Clock,
  History, LineChart, TrendingUp
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const NAV_SECTIONS = [
  {
    label: 'RESEARCH',
    items: [
      { to: '/', icon: Activity, label: 'Analysis' },
      { to: '/macro', icon: TrendingUp, label: 'Macro' },
    ],
  },
  {
    label: 'TOOLS',
    items: [
      { to: '/watchlist', icon: BarChart3, label: 'Watchlist' },
      { to: '/portfolio', icon: Briefcase, label: 'Holdings' },
      { to: '/schedules', icon: Clock, label: 'Schedules' },
      { to: '/alerts', icon: Bell, label: 'Alerts', badge: true },
    ],
  },
  {
    label: 'HISTORY',
    items: [
      { to: '/history', icon: History, label: 'History' },
      { to: '/inflections', icon: LineChart, label: 'Inflections' },
    ],
  },
]

const REC_COLORS = {
  BUY: 'var(--success)',
  'STRONG BUY': 'var(--success)',
  SELL: 'var(--danger)',
  'STRONG SELL': 'var(--danger)',
  HOLD: 'var(--warning)',
}

export default function Sidebar({ unacknowledgedCount = 0, recentAnalyses = [], onSelectTicker }) {
  return (
    <aside
      className="fixed left-0 z-30 flex flex-col border-r border-[var(--border)] overflow-y-auto"
      style={{
        top: 'var(--header-height)',
        bottom: 0,
        width: 'var(--sidebar-width)',
        backgroundColor: 'var(--sidebar-bg)',
      }}
    >
      {/* Navigation sections */}
      <nav className="flex-1 px-3 py-4 space-y-6">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-2 text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors relative',
                      isActive
                        ? 'bg-[var(--sidebar-active-bg)] text-[var(--primary)]'
                        : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.03)]'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <div
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                          style={{ backgroundColor: 'var(--primary)' }}
                        />
                      )}
                      <item.icon className="w-4 h-4 shrink-0" />
                      <span>{item.label}</span>
                      {item.badge && unacknowledgedCount > 0 && (
                        <Badge variant="destructive" className="ml-auto text-[10px] px-1.5 py-0">
                          {unacknowledgedCount}
                        </Badge>
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Recent analyses */}
      {recentAnalyses.length > 0 && (
        <div className="px-3 pb-4 border-t border-[var(--border)] pt-4">
          <p className="px-3 mb-2 text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase">
            Recent
          </p>
          <div className="space-y-0.5">
            {recentAnalyses.map((item) => (
              <button
                key={item.ticker}
                onClick={() => onSelectTicker?.(item.ticker)}
                className="flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm w-full text-left transition-colors text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[rgba(255,255,255,0.03)] cursor-pointer"
              >
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: REC_COLORS[item.recommendation?.toUpperCase()] || 'var(--text-muted)' }}
                />
                <span className="font-data text-xs">{item.ticker}</span>
                <span className="ml-auto text-[10px] text-[var(--text-muted)]">
                  {item.recommendation?.toUpperCase()}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  )
}
```

- [ ] **Step 3: Create AppLayout component**

Create `frontend/src/components/layout/AppLayout.jsx`:

```jsx
import { useState, useEffect, useCallback } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import { useAnalysisContext } from '@/context/AnalysisContext'
import { useAnalysis } from '@/hooks/useAnalysis'
import { getUnacknowledgedCount } from '@/utils/api'

export default function AppLayout() {
  const [tickerInput, setTickerInput] = useState('')
  const [unacknowledgedCount, setUnacknowledgedCount] = useState(0)
  const [recentAnalyses, setRecentAnalyses] = useState([])
  const { analysis } = useAnalysisContext()
  const { runAnalysis } = useAnalysis()
  const navigate = useNavigate()

  // Fetch alert count
  useEffect(() => {
    getUnacknowledgedCount()
      .then((data) => setUnacknowledgedCount(data?.count || 0))
      .catch(() => {})
    const interval = setInterval(() => {
      getUnacknowledgedCount()
        .then((data) => setUnacknowledgedCount(data?.count || 0))
        .catch(() => {})
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  // Track recent analyses
  useEffect(() => {
    if (analysis?.ticker && analysis?.recommendation) {
      setRecentAnalyses((prev) => {
        const filtered = prev.filter((a) => a.ticker !== analysis.ticker)
        return [
          { ticker: analysis.ticker, recommendation: analysis.recommendation },
          ...filtered,
        ].slice(0, 5)
      })
    }
  }, [analysis?.ticker, analysis?.recommendation])

  const handleAnalyze = useCallback(
    (e) => {
      e.preventDefault()
      const ticker = tickerInput.trim().toUpperCase()
      if (!ticker) return
      navigate(`/analysis/${ticker}`)
      runAnalysis(ticker)
    },
    [tickerInput, navigate, runAnalysis]
  )

  const handleSelectTicker = useCallback(
    (ticker) => {
      setTickerInput(ticker)
      navigate(`/analysis/${ticker}`)
      runAnalysis(ticker)
    },
    [navigate, runAnalysis]
  )

  return (
    <div className="h-screen overflow-hidden">
      <Header
        tickerInput={tickerInput}
        setTickerInput={setTickerInput}
        onAnalyze={handleAnalyze}
        unacknowledgedCount={unacknowledgedCount}
      />
      <Sidebar
        unacknowledgedCount={unacknowledgedCount}
        recentAnalyses={recentAnalyses}
        onSelectTicker={handleSelectTicker}
      />
      <main
        className="overflow-y-auto"
        style={{
          marginLeft: 'var(--sidebar-width)',
          marginTop: 'var(--header-height)',
          height: 'calc(100vh - var(--header-height))',
          padding: '24px',
        }}
      >
        <Outlet context={{ onSelectTicker: handleSelectTicker }} />
      </main>
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds (components exist but aren't wired in yet).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/layout/
git commit -m "feat: add AppLayout, Header, and Sidebar layout components"
```

---

## Task 5: Set Up React Router and Wire the App

**Files:**
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/hooks/useAnalysis.js`

- [ ] **Step 1: Update main.jsx to add BrowserRouter**

Replace `frontend/src/main.jsx`:

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { TooltipProvider } from '@/components/ui/tooltip'
import App from './App.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <TooltipProvider>
        <App />
      </TooltipProvider>
    </BrowserRouter>
  </StrictMode>,
)
```

- [ ] **Step 2: Replace App.jsx with route definitions**

Replace `frontend/src/App.jsx`:

```jsx
import { Routes, Route } from 'react-router-dom'
import { AnalysisProvider } from './context/AnalysisContext'
import AppLayout from './components/layout/AppLayout'
import AnalysisView from './components/analysis/AnalysisView'
import MacroPage from './components/views/MacroPage'
import HistoryView from './components/views/HistoryView'
import WatchlistView from './components/views/WatchlistView'
import PortfolioView from './components/views/PortfolioView'
import SchedulesView from './components/views/SchedulesView'
import AlertsView from './components/views/AlertsView'
import InflectionView from './components/views/InflectionView'

export default function App() {
  return (
    <AnalysisProvider>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<AnalysisView />} />
          <Route path="analysis/:ticker" element={<AnalysisView />} />
          <Route path="macro" element={<MacroPage />} />
          <Route path="history" element={<HistoryView />} />
          <Route path="watchlist" element={<WatchlistView />} />
          <Route path="portfolio" element={<PortfolioView />} />
          <Route path="schedules" element={<SchedulesView />} />
          <Route path="alerts" element={<AlertsView />} />
          <Route path="inflections" element={<InflectionView />} />
        </Route>
      </Routes>
    </AnalysisProvider>
  )
}
```

- [ ] **Step 3: Create stub AnalysisView**

Create `frontend/src/components/analysis/AnalysisView.jsx` as a minimal placeholder so routing works:

```jsx
import { useParams } from 'react-router-dom'
import { useAnalysisContext } from '@/context/AnalysisContext'

export default function AnalysisView() {
  const { ticker } = useParams()
  const { analysis, loading } = useAnalysisContext()

  if (!analysis && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center">
        <p className="text-2xl font-semibold text-[var(--text-primary)] mb-2">
          Enter a ticker above to start analysis
        </p>
        <p className="text-sm text-[var(--muted-foreground)]">
          Search for any stock symbol to get AI-powered research
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">
        {analysis?.ticker || ticker} Analysis
      </h1>
      <p className="text-[var(--muted-foreground)]">
        {loading ? 'Analyzing...' : 'Analysis complete — tabs coming in next task.'}
      </p>
    </div>
  )
}
```

- [ ] **Step 4: Move existing view files to views/ directory**

```bash
cd frontend/src/components
# Copy view files to views/ directory (keep originals for now as fallback)
cp MacroPage.jsx views/MacroPage.jsx
cp HistoryView.jsx views/HistoryView.jsx
cp WatchlistView.jsx views/WatchlistView.jsx
cp PortfolioView.jsx views/PortfolioView.jsx
cp SchedulesView.jsx views/SchedulesView.jsx
cp AlertsView.jsx views/AlertsView.jsx
cp InflectionView.jsx views/InflectionView.jsx
cp InflectionChart.jsx views/InflectionChart.jsx
cp InflectionHeatmap.jsx views/InflectionHeatmap.jsx
cp InflectionFeed.jsx views/InflectionFeed.jsx
```

- [ ] **Step 5: Update import paths in moved view files**

Each moved view file needs its relative imports updated. For example, in each file under `views/`:
- Change `import { ... } from './Icons'` → `import { ... } from '../panels/Icons'`
- Change `import InflectionChart from './InflectionChart'` → `import InflectionChart from './InflectionChart'` (same directory, no change needed for sibling imports within views/)
- Change any `from '../../utils/api'` or `from '../../hooks/...'` — use `@/` aliases instead:
  - `import { ... } from '@/utils/api'`
  - `import { ... } from '@/hooks/useHistory'`
  - `import { ... } from '@/context/AnalysisContext'`

Repeat for all view files. The key changes per file:

**HistoryView.jsx**: Update `useHistory` import to `@/hooks/useHistory`, Icons import to `../panels/Icons`
**WatchlistView.jsx**: Update api import to `@/utils/api`, Icons import to `../panels/Icons`
**PortfolioView.jsx**: Update api import to `@/utils/api`, Icons import to `../panels/Icons`
**SchedulesView.jsx**: Update api import to `@/utils/api`, Icons import to `../panels/Icons`
**AlertsView.jsx**: Update api import to `@/utils/api`, Icons import to `../panels/Icons`
**MacroPage.jsx**: Update api import to `@/utils/api`
**InflectionView.jsx**: Update imports for InflectionChart, InflectionHeatmap, InflectionFeed (same dir), api to `@/utils/api`
**InflectionChart.jsx**: Update api import to `@/utils/api`
**InflectionHeatmap.jsx**: Update api import to `@/utils/api`
**InflectionFeed.jsx**: Update api import to `@/utils/api`

- [ ] **Step 6: Move panel files to panels/ directory**

```bash
cd frontend/src/components
cp CompanyOverview.jsx panels/CompanyOverview.jsx
cp ThesisPanel.jsx panels/ThesisPanel.jsx
cp NarrativePanel.jsx panels/NarrativePanel.jsx
cp RiskDiffPanel.jsx panels/RiskDiffPanel.jsx
cp EarningsReviewPanel.jsx panels/EarningsReviewPanel.jsx
cp EarningsPanel.jsx panels/EarningsPanel.jsx
cp PriceChart.jsx panels/PriceChart.jsx
cp TechnicalsOptionsSection.jsx panels/TechnicalsOptionsSection.jsx
cp NewsFeed.jsx panels/NewsFeed.jsx
cp OptionsFlow.jsx panels/OptionsFlow.jsx
cp LeadershipPanel.jsx panels/LeadershipPanel.jsx
cp CouncilPanel.jsx panels/CouncilPanel.jsx
cp MetaFooter.jsx panels/MetaFooter.jsx
cp Icons.jsx panels/Icons.jsx
```

Update panel imports similarly — use `@/` aliases for utils/hooks/context, and relative paths for sibling panel imports.

- [ ] **Step 7: Verify the app loads with new routing**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173` — you should see the new layout (Header + Sidebar + empty analysis view). Navigate to `/macro`, `/history`, etc. — each should load the corresponding view.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: wire React Router with AppLayout and move files to new structure"
```

---

## Task 6: Build KPI Row and KPI Card Components

**Files:**
- Create: `frontend/src/components/analysis/KpiCard.jsx`
- Create: `frontend/src/components/analysis/KpiRow.jsx`

- [ ] **Step 1: Create KpiCard component**

Create `frontend/src/components/analysis/KpiCard.jsx`:

```jsx
import { Card } from '@/components/ui/card'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function KpiCard({ icon: Icon, label, value, trend, trendLabel, className }) {
  const isPositive = trend > 0
  const isNegative = trend < 0
  const TrendIcon = isPositive ? TrendingUp : TrendingDown

  return (
    <Card className={cn('p-4 relative overflow-hidden', className)}>
      <div className="flex items-start justify-between mb-3">
        {/* Icon */}
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ backgroundColor: 'rgba(232, 134, 12, 0.1)' }}
        >
          <Icon className="w-4.5 h-4.5 text-[var(--primary)]" />
        </div>

        {/* Trend indicator */}
        {trend !== undefined && trend !== null && (
          <div
            className={cn(
              'flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded',
              isPositive && 'text-[var(--success)] bg-[rgba(23,201,100,0.1)]',
              isNegative && 'text-[var(--danger)] bg-[rgba(243,18,96,0.1)]',
              !isPositive && !isNegative && 'text-[var(--muted-foreground)]'
            )}
          >
            {(isPositive || isNegative) && <TrendIcon className="w-3 h-3" />}
            <span>{isPositive ? '+' : ''}{typeof trend === 'number' ? trend.toFixed(1) : trend}%</span>
          </div>
        )}
      </div>

      {/* Label */}
      <p className="text-xs text-[var(--muted-foreground)] mb-1">{label}</p>

      {/* Value */}
      <p className="text-2xl font-semibold font-data text-[var(--text-primary)]">{value}</p>

      {/* Trend label */}
      {trendLabel && (
        <p className="text-[11px] text-[var(--text-muted)] mt-1">{trendLabel}</p>
      )}
    </Card>
  )
}
```

- [ ] **Step 2: Create KpiRow component**

Create `frontend/src/components/analysis/KpiRow.jsx`:

```jsx
import { DollarSign, Target, Gauge, TrendingUp, BarChart3 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import KpiCard from './KpiCard'

const REC_VARIANT = {
  BUY: 'success',
  'STRONG BUY': 'success',
  SELL: 'danger',
  'STRONG SELL': 'danger',
  HOLD: 'warning',
}

function formatPrice(price) {
  if (!price && price !== 0) return '—'
  return '$' + Number(price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatPct(val) {
  if (!val && val !== 0) return '—'
  return Number(val).toFixed(1) + '%'
}

export default function KpiRow({ analysis }) {
  if (!analysis) return null

  const market = analysis.agent_results?.market?.data || {}
  const fundamentals = analysis.agent_results?.fundamentals?.data || {}
  const sentiment = analysis.agent_results?.sentiment?.data || analysis.analysis?.sentiment || {}
  const recommendation = analysis.signal_contract_v2?.recommendation || analysis.recommendation || '—'
  const confidence = analysis.confidence_score ?? analysis.signal_contract_v2?.confidence

  const price = market.current_price || market.price
  const change1d = market.change_1d ?? market.percent_change
  const sentimentScore = sentiment.overall_score ?? sentiment.composite_score
  const pe = fundamentals.pe_ratio ?? fundamentals.pe

  return (
    <div className="grid grid-cols-5 gap-4 mb-6">
      <KpiCard
        icon={DollarSign}
        label="Price"
        value={formatPrice(price)}
        trend={change1d}
      />

      {/* Recommendation — custom card since value is a badge */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex items-start justify-between mb-3">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: 'rgba(232, 134, 12, 0.1)' }}
          >
            <Target className="w-4.5 h-4.5 text-[var(--primary)]" />
          </div>
        </div>
        <p className="text-xs text-[var(--muted-foreground)] mb-1">Rating</p>
        <Badge variant={REC_VARIANT[recommendation?.toUpperCase()] || 'secondary'} className="text-base px-3 py-0.5">
          {recommendation}
        </Badge>
      </div>

      <KpiCard
        icon={Gauge}
        label="Confidence"
        value={confidence != null ? `${Math.round(confidence)}%` : '—'}
        trendLabel={confidence != null ? 'AI confidence score' : undefined}
      />

      <KpiCard
        icon={TrendingUp}
        label="Sentiment"
        value={sentimentScore != null ? (sentimentScore > 0 ? '+' : '') + sentimentScore.toFixed(2) : '—'}
        trendLabel={
          sentimentScore != null
            ? sentimentScore > 0.3 ? 'Bullish'
            : sentimentScore < -0.3 ? 'Bearish'
            : 'Neutral'
            : undefined
        }
      />

      <KpiCard
        icon={BarChart3}
        label="P/E Ratio"
        value={pe != null ? pe.toFixed(1) + 'x' : '—'}
        trendLabel="Price to earnings"
      />
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/analysis/KpiCard.jsx frontend/src/components/analysis/KpiRow.jsx
git commit -m "feat: add KPI row and card components for analysis summary"
```

---

## Task 7: Build Analysis Tabs and Tab Content Components

**Files:**
- Create: `frontend/src/components/analysis/AnalysisTabs.jsx`
- Create: `frontend/src/components/analysis/OverviewTab.jsx`
- Create: `frontend/src/components/analysis/ThesisRiskTab.jsx`
- Create: `frontend/src/components/analysis/TechnicalsTab.jsx`
- Create: `frontend/src/components/analysis/SentimentTab.jsx`
- Create: `frontend/src/components/analysis/CouncilTab.jsx`
- Modify: `frontend/src/components/analysis/AnalysisView.jsx`

- [ ] **Step 1: Create AnalysisTabs**

Create `frontend/src/components/analysis/AnalysisTabs.jsx`:

```jsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import OverviewTab from './OverviewTab'
import ThesisRiskTab from './ThesisRiskTab'
import TechnicalsTab from './TechnicalsTab'
import SentimentTab from './SentimentTab'
import CouncilTab from './CouncilTab'
import { motion, AnimatePresence } from 'framer-motion'

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'thesis', label: 'Thesis & Risk' },
  { value: 'technicals', label: 'Technicals' },
  { value: 'sentiment', label: 'Sentiment' },
  { value: 'council', label: 'Council' },
]

export default function AnalysisTabs({ analysis }) {
  return (
    <Tabs defaultValue="overview" className="w-full">
      <TabsList className="w-full justify-start bg-transparent border-b border-[var(--border)] rounded-none p-0 h-auto gap-0">
        {TABS.map((tab) => (
          <TabsTrigger
            key={tab.value}
            value={tab.value}
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--primary)] data-[state=active]:bg-transparent data-[state=active]:text-[var(--text-primary)] data-[state=active]:shadow-none px-4 py-2.5 text-sm"
          >
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>

      <TabsContent value="overview">
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
          <OverviewTab analysis={analysis} />
        </motion.div>
      </TabsContent>

      <TabsContent value="thesis">
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
          <ThesisRiskTab analysis={analysis} />
        </motion.div>
      </TabsContent>

      <TabsContent value="technicals">
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
          <TechnicalsTab analysis={analysis} />
        </motion.div>
      </TabsContent>

      <TabsContent value="sentiment">
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
          <SentimentTab analysis={analysis} />
        </motion.div>
      </TabsContent>

      <TabsContent value="council">
        <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
          <CouncilTab analysis={analysis} />
        </motion.div>
      </TabsContent>
    </Tabs>
  )
}
```

- [ ] **Step 2: Create OverviewTab**

Create `frontend/src/components/analysis/OverviewTab.jsx`:

```jsx
import CompanyOverview from '@/components/panels/CompanyOverview'
import EarningsPanel from '@/components/panels/EarningsPanel'
import PriceChart from '@/components/panels/PriceChart'

export default function OverviewTab({ analysis }) {
  return (
    <div className="space-y-6">
      <CompanyOverview analysis={analysis} />
      <EarningsPanel analysis={analysis} />
      <PriceChart analysis={analysis} />
    </div>
  )
}
```

- [ ] **Step 3: Create ThesisRiskTab**

Create `frontend/src/components/analysis/ThesisRiskTab.jsx`:

```jsx
import ThesisPanel from '@/components/panels/ThesisPanel'
import NarrativePanel from '@/components/panels/NarrativePanel'
import RiskDiffPanel from '@/components/panels/RiskDiffPanel'
import EarningsReviewPanel from '@/components/panels/EarningsReviewPanel'

export default function ThesisRiskTab({ analysis }) {
  const hasThesis = analysis?.analysis?.thesis
  const hasNarrative = analysis?.analysis?.narrative
  const hasRiskDiff = analysis?.analysis?.risk_diff
  const hasEarningsReview = analysis?.analysis?.earnings_review

  return (
    <div className="space-y-6">
      {hasThesis && <ThesisPanel analysis={analysis} />}
      {hasNarrative && <NarrativePanel analysis={analysis} />}
      {hasRiskDiff && <RiskDiffPanel analysis={analysis} />}
      {hasEarningsReview && <EarningsReviewPanel analysis={analysis} />}
      {!hasThesis && !hasNarrative && !hasRiskDiff && !hasEarningsReview && (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <p>No thesis or risk data available for this analysis.</p>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create TechnicalsTab**

Create `frontend/src/components/analysis/TechnicalsTab.jsx`:

```jsx
import TechnicalsOptionsSection from '@/components/panels/TechnicalsOptionsSection'
import PriceChart from '@/components/panels/PriceChart'

export default function TechnicalsTab({ analysis }) {
  return (
    <div className="space-y-6">
      <PriceChart analysis={analysis} />
      <TechnicalsOptionsSection analysis={analysis} />
    </div>
  )
}
```

- [ ] **Step 5: Create SentimentTab**

Create `frontend/src/components/analysis/SentimentTab.jsx`:

```jsx
import NewsFeed from '@/components/panels/NewsFeed'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

function SentimentBreakdown({ sentiment }) {
  if (!sentiment) return null

  const factors = sentiment.factors || sentiment.factor_scores || []
  const overall = sentiment.overall_score ?? sentiment.composite_score
  const analysis = sentiment.analysis || sentiment.summary

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Sentiment Analysis</CardTitle>
          {overall != null && (
            <Badge variant={overall > 0.3 ? 'success' : overall < -0.3 ? 'danger' : 'warning'}>
              {overall > 0 ? '+' : ''}{overall.toFixed(2)}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {analysis && (
          <p className="text-sm text-[var(--text-secondary)] mb-4">{analysis}</p>
        )}
        {factors.length > 0 && (
          <div className="space-y-3">
            {factors.map((factor, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-sm text-[var(--text-secondary)]">
                  {factor.name || factor.factor}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-24 h-1.5 rounded-full bg-[var(--muted)] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.abs((factor.score || factor.weight || 0) * 100)}%`,
                        backgroundColor: (factor.score || 0) > 0 ? 'var(--success)' : 'var(--danger)',
                      }}
                    />
                  </div>
                  <span className="font-data text-xs w-10 text-right text-[var(--text-muted)]">
                    {(factor.score || factor.weight || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function MacroSummary({ macro }) {
  if (!macro) return null

  const indicators = macro.indicators || []
  const summary = macro.analysis || macro.summary

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Macro Environment</CardTitle>
      </CardHeader>
      <CardContent>
        {summary && (
          <p className="text-sm text-[var(--text-secondary)] mb-4">{summary}</p>
        )}
        {indicators.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {indicators.map((ind, i) => (
              <div key={i} className="flex justify-between items-center py-1.5 border-b border-[var(--border)] last:border-0">
                <span className="text-xs text-[var(--text-muted)]">{ind.name}</span>
                <span className="font-data text-sm">{ind.value}</span>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function SentimentTab({ analysis }) {
  const sentiment = analysis?.agent_results?.sentiment?.data
  const macro = analysis?.agent_results?.macro?.data

  return (
    <div className="space-y-6">
      <SentimentBreakdown sentiment={sentiment} />
      <NewsFeed analysis={analysis} />
      <MacroSummary macro={macro} />
    </div>
  )
}
```

- [ ] **Step 6: Create CouncilTab**

Create `frontend/src/components/analysis/CouncilTab.jsx`:

```jsx
import CouncilPanel from '@/components/panels/CouncilPanel'
import LeadershipPanel from '@/components/panels/LeadershipPanel'

export default function CouncilTab({ analysis }) {
  return (
    <div className="space-y-6">
      <CouncilPanel analysis={analysis} ticker={analysis?.ticker} />
      <LeadershipPanel analysis={analysis} />
    </div>
  )
}
```

- [ ] **Step 7: Update AnalysisView to use KpiRow + AnalysisTabs**

Replace `frontend/src/components/analysis/AnalysisView.jsx`:

```jsx
import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useAnalysisContext } from '@/context/AnalysisContext'
import { useAnalysis } from '@/hooks/useAnalysis'
import { Skeleton } from '@/components/ui/skeleton'
import KpiRow from './KpiRow'
import AnalysisTabs from './AnalysisTabs'
import MetaFooter from '@/components/panels/MetaFooter'
import { motion } from 'framer-motion'

export default function AnalysisView() {
  const { ticker } = useParams()
  const { analysis, loading } = useAnalysisContext()
  const { fetchLatest } = useAnalysis()

  // If navigating to /analysis/:ticker directly, try loading cached analysis
  useEffect(() => {
    if (ticker && !analysis && !loading) {
      fetchLatest(ticker)
    }
  }, [ticker])

  // Welcome state
  if (!analysis && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-center">
        <div className="w-16 h-16 rounded-2xl bg-[var(--secondary)] flex items-center justify-center mb-6">
          <span className="text-3xl text-[var(--primary)]">$</span>
        </div>
        <p className="text-xl font-semibold text-[var(--text-primary)] mb-2">
          Enter a ticker to start analysis
        </p>
        <p className="text-sm text-[var(--muted-foreground)] max-w-md">
          Search for any stock symbol above to get AI-powered market research with insights from 9 specialized agents.
        </p>
      </div>
    )
  }

  // Loading skeleton state
  if (loading && !analysis) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-10 w-96 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <KpiRow analysis={analysis} />
      <AnalysisTabs analysis={analysis} />
      <MetaFooter analysis={analysis} />
    </motion.div>
  )
}
```

- [ ] **Step 8: Verify the app loads and tabs work**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173`, enter a ticker, verify:
- KPI row appears with 5 stat cards
- 5 tabs render below
- Clicking tabs switches content
- Each tab shows the correct panels

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/analysis/
git commit -m "feat: add analysis tabs, KPI row, and tab content components"
```

---

## Task 8: Migrate Panel Components — Restyle with shadcn Cards

**Files:**
- Modify: All files in `frontend/src/components/panels/`

This task restyles each panel to use shadcn `Card` instead of glass-card classes, updates typography to Inter/Fira Code, and replaces inline color values with CSS variable references. The logic and data extraction in each panel stays the same.

The key changes applied to every panel:

1. Replace `<div className="glass-card ...">` → `<Card>` / `<CardHeader>` / `<CardContent>`
2. Replace hardcoded colors (`#17c964`, `#f31260`, `#006fee`) → CSS variables (`var(--success)`, `var(--danger)`, `var(--primary)`)
3. Add `font-data` class to all numeric/data values
4. Replace custom badge divs → shadcn `<Badge>`
5. Update imports to use `@/` aliases

- [ ] **Step 1: Update CompanyOverview.jsx**

In `frontend/src/components/panels/CompanyOverview.jsx`, make these changes:

Add imports at top:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
```

Replace all `<div className="glass-card ..."` with `<Card>` wrappers. Replace inline `style={{ color: '#17c964' }}` with `style={{ color: 'var(--success)' }}`. Add `font-data` class to all numeric values (market cap, P/E, EPS, etc.).

- [ ] **Step 2: Update EarningsPanel.jsx**

In `frontend/src/components/panels/EarningsPanel.jsx`:

Add imports:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
```

Replace glass-card divs with Card components. Replace tag badges (BEAT, MISS, NEW, WATCH) with `<Badge variant="success">`, `<Badge variant="danger">`, etc. Add `font-data` to EPS values and tone percentages.

- [ ] **Step 3: Update EarningsReviewPanel.jsx**

In `frontend/src/components/panels/EarningsReviewPanel.jsx`:

Add imports:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
```

Replace glass-card divs with Card. Replace KPI table HTML with shadcn Table components. Replace inline badge styles with Badge variants.

- [ ] **Step 4: Update ThesisPanel.jsx**

In `frontend/src/components/panels/ThesisPanel.jsx`:

Add imports:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
```

Replace glass-card divs with Card. Replace bull/bear card backgrounds: bull uses `bg-[rgba(23,201,100,0.05)]`, bear uses `bg-[rgba(243,18,96,0.05)]`. Replace retry button with shadcn Button.

- [ ] **Step 5: Update NarrativePanel.jsx**

In `frontend/src/components/panels/NarrativePanel.jsx`:

Add imports:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
```

Replace glass-card divs with Card. Add `font-data` to year labels and numeric values.

- [ ] **Step 6: Update RiskDiffPanel.jsx**

In `frontend/src/components/panels/RiskDiffPanel.jsx`:

Add imports:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
```

Replace glass-card divs with Card. Replace risk inventory table with shadcn Table. Replace severity badges with Badge variant mapping: HIGH → danger, MEDIUM → warning, LOW → secondary.

- [ ] **Step 7: Update TechnicalsOptionsSection.jsx and OptionsFlow.jsx**

In both files, add Card imports and replace glass-card divs. Add `font-data` to RSI values, MACD numbers, P/C ratios, max pain price.

- [ ] **Step 8: Update NewsFeed.jsx**

In `frontend/src/components/panels/NewsFeed.jsx`:

Add imports:
```jsx
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
```

Replace glass-card article cards with Card. Replace sentiment score badges with Badge variants.

- [ ] **Step 9: Update LeadershipPanel.jsx**

In `frontend/src/components/panels/LeadershipPanel.jsx`:

Add Card, Badge, Button imports. Replace glass-card divs. Replace grade badges with Badge components. Add `font-data` to score values.

- [ ] **Step 10: Update CouncilPanel.jsx**

In `frontend/src/components/panels/CouncilPanel.jsx`:

Add Card, Badge, Button, Dialog imports. Replace glass-card divs with Card. Replace the AddVoiceModal with shadcn Dialog. Replace stance badges with Badge variants. Replace the thesis form inputs with shadcn Input. This is the largest panel (862 lines) — keep all logic, just restyle the JSX.

- [ ] **Step 11: Update PriceChart.jsx**

In `frontend/src/components/panels/PriceChart.jsx`:

Add Card imports. Wrap the chart container and metric cards in Card components. Update the chart's background color to match `--card` (#141414). Update grid line colors to use `--border`. Keep all Lightweight Charts logic unchanged.

Specifically, update the `createChart` config:
```javascript
layout: {
  background: { type: 'solid', color: '#141414' },
  textColor: 'rgba(255, 255, 255, 0.6)',
},
grid: {
  vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
  horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
},
```

- [ ] **Step 12: Update MetaFooter.jsx**

In `frontend/src/components/panels/MetaFooter.jsx`:

Add Card, Badge, Button imports. Replace the footer strip with a Card. Replace the diagnostics slide-over with a shadcn Dialog.

- [ ] **Step 13: Verify the app renders all panels correctly**

```bash
cd frontend && npm run dev
```

Run an analysis and verify each tab's panels render with the new Card styling. Check that:
- Cards have `#141414` background with subtle borders
- Data values use monospace font
- Badges show correct colors
- No broken layouts or missing content

- [ ] **Step 14: Commit**

```bash
git add frontend/src/components/panels/
git commit -m "feat: restyle all panels with shadcn Card, Badge, Table components"
```

---

## Task 9: Restyle Secondary Views

**Files:**
- Modify: All files in `frontend/src/components/views/`

Apply the same shadcn component treatment to the secondary views: MacroPage, HistoryView, WatchlistView, PortfolioView, SchedulesView, AlertsView, InflectionView.

- [ ] **Step 1: Update MacroPage.jsx**

Replace glass-card metric cards with shadcn Card. Add `font-data` to indicator values. Use Badge for status indicators.

- [ ] **Step 2: Update HistoryView.jsx**

Replace filter buttons with shadcn Button (variant toggle pattern). Replace history list items with Card components. Use shadcn Input for search. Use Badge for recommendation labels.

- [ ] **Step 3: Update WatchlistView.jsx**

Replace the left sidebar list with Card-wrapped items. Replace the MiniCard ticker cards with shadcn Card. Replace forms with shadcn Input + Button. Replace the batch progress bar with the new progress-bar CSS class.

- [ ] **Step 4: Update PortfolioView.jsx**

Replace the holdings table with shadcn Table (TableHeader, TableBody, TableRow, TableCell, TableHead). Replace the SummaryStrip cards with shadcn Card. Replace form inputs with shadcn Input + Button + Select.

- [ ] **Step 5: Update SchedulesView.jsx**

Replace schedule cards with shadcn Card. Replace the create form with Input + Select + Button. Replace the toggle switch with a styled checkbox or Button toggle. Replace run history rows with a shadcn Table.

- [ ] **Step 6: Update AlertsView.jsx**

Replace rule cards with shadcn Card + Badge. Replace notification rows with Card. Replace the create form with Input + Select + Button. Replace severity dots with Badge variants.

- [ ] **Step 7: Update InflectionView.jsx, InflectionChart.jsx, InflectionHeatmap.jsx, InflectionFeed.jsx**

Replace glass-card wrappers with Card. Update InflectionChart's chart config to use `--card` background and `--border` grid colors (same as PriceChart). Replace heatmap bar colors to use CSS variables.

- [ ] **Step 8: Verify all secondary views**

```bash
cd frontend && npm run dev
```

Navigate to each view (/macro, /history, /watchlist, /portfolio, /schedules, /alerts, /inflections) and verify:
- Cards render with correct backgrounds
- Tables are aligned and readable
- Forms are functional
- Badges show correct colors

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/views/
git commit -m "feat: restyle secondary views with shadcn components"
```

---

## Task 10: Clean Up — Remove Old Files and Dead Code

**Files:**
- Delete: Old component files in `frontend/src/components/` (root level)
- Modify: `frontend/tailwind.config.js` (simplify)

- [ ] **Step 1: Remove old component files**

```bash
cd frontend/src/components
rm -f Dashboard.jsx Sidebar.jsx SearchBar.jsx SectionNav.jsx ThesisCard.jsx AnalysisSection.jsx
rm -f CompanyOverview.jsx ThesisPanel.jsx NarrativePanel.jsx RiskDiffPanel.jsx
rm -f EarningsReviewPanel.jsx EarningsPanel.jsx PriceChart.jsx TechnicalsOptionsSection.jsx
rm -f NewsFeed.jsx OptionsFlow.jsx LeadershipPanel.jsx CouncilPanel.jsx MetaFooter.jsx Icons.jsx
rm -f MacroPage.jsx HistoryView.jsx WatchlistView.jsx PortfolioView.jsx
rm -f SchedulesView.jsx AlertsView.jsx InflectionView.jsx
rm -f InflectionChart.jsx InflectionHeatmap.jsx InflectionFeed.jsx
```

- [ ] **Step 2: Update tailwind.config.js**

Replace `frontend/tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 3: Verify full build and no broken imports**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no warnings about missing modules.

- [ ] **Step 4: Test the full app**

```bash
cd frontend && npm run dev
```

Verify:
- All routes work (/analysis/AAPL, /macro, /history, /watchlist, /portfolio, /schedules, /alerts, /inflections)
- Analysis flow: enter ticker → progress bar → KPI row + tabs
- All 5 tabs show correct content
- Sidebar navigation highlights active route
- Recent analyses appear in sidebar
- Alert badge count shows in sidebar and header
- No console errors

- [ ] **Step 5: Commit**

```bash
git add -A frontend/
git commit -m "chore: remove old components and clean up tailwind config"
```

---

## Task 11: Polish — Animations, Loading States, Edge Cases

**Files:**
- Modify: Various files for final polish

- [ ] **Step 1: Add stagger animation to KPI cards**

In `frontend/src/components/analysis/KpiRow.jsx`, wrap each KpiCard in a `motion.div` with stagger:

```jsx
import { motion } from 'framer-motion'

// In the return, wrap each card:
<motion.div
  initial={{ opacity: 0, y: 8 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.2, delay: index * 0.05 }}
>
  <KpiCard ... />
</motion.div>
```

- [ ] **Step 2: Add tab transition animation**

The AnalysisTabs already has motion.div wrappers. Verify they provide smooth 150ms fade transitions when switching tabs.

- [ ] **Step 3: Add empty states to all tabs**

Verify each tab shows a helpful empty message when its data is missing:
- OverviewTab: "No overview data available"
- ThesisRiskTab: Already has empty state (Step 3 of Task 7)
- TechnicalsTab: "No technical data available"
- SentimentTab: "No sentiment data available"
- CouncilTab: CouncilPanel handles its own empty/trigger state

- [ ] **Step 4: Verify skeleton loading states**

In `AnalysisView.jsx`, verify the skeleton grid renders correctly during initial loading. The 5 skeleton cards should match the KPI row dimensions.

- [ ] **Step 5: Test responsive behavior**

Resize the browser to verify:
- Sidebar stays fixed at 220px
- Main content fills remaining width
- KPI cards stack or shrink gracefully at narrow widths
- Charts resize via their ResizeObserver

- [ ] **Step 6: Final commit**

```bash
git add -A frontend/
git commit -m "feat: add polish — animations, loading states, empty states"
```

---

## Summary

| Task | Description | Key Deliverable |
|------|-------------|-----------------|
| 1 | Install deps + shadcn foundation | Dependencies, cn(), path aliases |
| 2 | Create shadcn UI primitives | 11 component files in ui/ |
| 3 | Replace design tokens | New warm dark palette in index.css |
| 4 | Build layout components | AppLayout, Header, Sidebar |
| 5 | Set up React Router | Routes, file moves, import updates |
| 6 | Build KPI components | KpiCard, KpiRow |
| 7 | Build analysis tabs | AnalysisTabs + 5 tab content components |
| 8 | Restyle panels | All panels use shadcn Card/Badge/Table |
| 9 | Restyle secondary views | All views use shadcn components |
| 10 | Clean up | Remove old files, simplify config |
| 11 | Polish | Animations, loading, empty states |
