// Who is signed in, if anyone. Signing in is optional, so `me.user` is often null.

import { useEffect, useState } from 'react'
import { getMe } from './api'
import type { Me } from './api'

const SIGNED_OUT: Me = { user: null, friends: [] }

/** The signed-in user and their saved friends. `setMe` takes the fresh value the account
 * endpoints return, so the screen updates without another request. */
export function useMe() {
  const [me, setMe] = useState<Me>(SIGNED_OUT)
  useEffect(() => {
    getMe()
      .then(setMe)
      .catch(() => setMe(SIGNED_OUT)) // the account isn't needed to split, so carry on signed out
  }, [])
  return [me, setMe] as const
}
