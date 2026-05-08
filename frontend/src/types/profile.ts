export type Profile = {
  name: string
  email: string
  initial: string
  avatar_url: string
}

export type ProfileResponse = {
  ok: boolean
  profile: Profile
  error?: string
}
