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

import { beforeEach, describe, expect, it } from 'vitest';
import { getAuthStore } from '../../../src/store/authStore';

describe('authStore', () => {
  beforeEach(() => {
    getAuthStore().logout();
  });

  it('normalizes access_token responses into the websocket token field', () => {
    getAuthStore().setAuth({
      access_token: 'Bearer backend-jwt',
      email: 'user@example.com',
      username: 'user',
      user_id: 1,
    } as any);

    expect(getAuthStore().token).toBe('backend-jwt');
  });
});
