// ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

import * as CheckboxPrimitives from '@radix-ui/react-checkbox';
import { Check } from 'lucide-react';
import * as React from 'react';

import { cn } from '@/lib/utils';
import { checkboxTokenAliases, mergeAliasStyles } from './tokenAliases';

export type CheckboxProps = React.ComponentPropsWithoutRef<
  typeof CheckboxPrimitives.Root
> & {
  iconClassName?: string;
};

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitives.Root>,
  CheckboxProps
>(({ className, style, iconClassName, ...props }, ref) => (
  <CheckboxPrimitives.Root
    ref={ref}
    className={cn(
      'group/checkbox peer h-4 w-4 shrink-0 rounded border border-solid border-ds-border-neutral-default-default bg-ds-bg-neutral-default-default transition-colors hover:border-ds-border-neutral-strong-default focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ds-ring-brand-default-focus focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:border-ds-border-status-completed-default-default data-[state=checked]:bg-ds-bg-success-default-default',
      className
    )}
    style={mergeAliasStyles(checkboxTokenAliases, style)}
    {...props}
  >
    <CheckboxPrimitives.Indicator className="flex items-center justify-center">
      <Check
        className={cn(
          'h-3.5 w-3.5 shrink-0 group-data-[state=checked]/checkbox:text-ds-text-brand-inverse-default',
          iconClassName
        )}
      />
    </CheckboxPrimitives.Indicator>
  </CheckboxPrimitives.Root>
));
Checkbox.displayName = CheckboxPrimitives.Root.displayName;

export { Checkbox };
