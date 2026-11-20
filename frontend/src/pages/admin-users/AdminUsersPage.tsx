import { useState } from "react"
import {
  ActionIcon,
  Button,
  Group,
  List,
  Modal,
  PasswordInput,
  ScrollArea,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Tooltip,
} from "@mantine/core"
import { notifications } from "@mantine/notifications"
import { IconAlertTriangle, IconKey, IconSearch, IconTrash, IconUserPlus } from "@tabler/icons-react"
import type { Role, User, UserWithToken } from "@/shared/api"

import { TokenModal, useCreateUser, useDeleteUser, useReissueToken, useUpdateUser, useUsers } from "@/features/admin"
import { ALL_ROLES } from "@/features/auth"
import { HttpError, useOrgUnits, useSession } from "@/shared/api"
import { rankByQuery, roleMeta, useDebouncedSearch } from "@/shared/lib"
import { PageHeader, QueryError, SearchSelect, Section, Seo } from "@/shared/ui"

const roleOptions = ALL_ROLES.map(r => ({ value: r, label: roleMeta[r].label }))

export function AdminUsersPage() {
  const users = useUsers()
  const units = useOrgUnits()
  const create = useCreateUser()
  const update = useUpdateUser()
  const reissue = useReissueToken()
  const remove = useDeleteUser()
  const { user: me } = useSession()
  const [deleting, setDeleting] = useState<User | null>(null)
  const [tokenFor, setTokenFor] = useState<User | null>(null)
  const [promoting, setPromoting] = useState<{
    name: string
    mode: "grant" | "revoke"
    newRole: Role
    apply: (adminPassword?: string) => Promise<unknown>
  } | null>(null)
  const [secret, setSecret] = useState("")
  const [secretError, setSecretError] = useState<string | null>(null)
  const [granting, setGranting] = useState(false)
  const resetSecret = () => {
    setSecret("")
    setSecretError(null)
  }
  const closeGrant = () => {
    setPromoting(null)
    resetSecret()
  }
  const closeTokenFor = () => {
    setTokenFor(null)
    resetSecret()
  }
  const confirmTokenFor = () =>
    tokenFor &&
    withSecret(() => reissue.mutateAsync({ id: tokenFor.id, adminPassword: secret }).then(setToken), closeTokenFor)
  const closeDelete = () => {
    setDeleting(null)
    resetSecret()
  }
  const withSecret = async (action: () => Promise<unknown>, close: () => void) => {
    setGranting(true)
    try {
      await action()
      close()
    } catch (e) {
      if (e instanceof HttpError && e.status === 403) setSecretError("Невірний секретний пароль")
      else fail(e as Error)
    } finally {
      setGranting(false)
    }
  }
  const confirmGrant = () => promoting && withSecret(() => promoting.apply(secret), closeGrant)
  const deletingAdmin = deleting?.role === "ADMIN"
  const confirmDelete = () =>
    deleting &&
    withSecret(
      () =>
        remove
          .mutateAsync({ id: deleting.id, adminPassword: deletingAdmin ? secret : undefined })
          .then(() =>
            notifications.show({ color: "success", message: `Користувача «${deleting.displayName}» видалено` })
          ),
      closeDelete
    )
  const secretInput = (description: string) => (
    <PasswordInput
      label='Секретний пароль підтвердження'
      description={description}
      value={secret}
      onChange={e => {
        const value = e.currentTarget.value
        setSecret(value)
        setSecretError(null)
      }}
      error={secretError}
      autoComplete='off'
      data-autofocus
      required
    />
  )
  const [token, setToken] = useState<UserWithToken | null>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<{ displayName: string; role: Role; orgUnitId: string | null }>({
    displayName: "",
    role: "EXECUTOR",
    orgUnitId: null,
  })
  const unitOptions = (units.data ?? []).map(u => ({ value: u.id, label: u.name }))
  const unitName = new Map(unitOptions.map(o => [o.value, o.label]))
  const search = useDebouncedSearch()
  const rows = search.query
    ? rankByQuery(
        users.data ?? [],
        search.query,
        u => `${u.displayName} ${roleMeta[u.role].label} ${unitName.get(u.orgUnitId) ?? ""}`
      )
    : (users.data ?? [])
  const fail = (e: Error) => notifications.show({ color: "danger", message: e.message })

  return (
    <>
      <Seo title='Користувачі' />
      <PageHeader
        title='Користувачі'
        description='Ролі, належність до підрозділу, видача і перевипуск персональних токенів, видалення облікових записів'
        actions={
          <Button
            leftSection={<IconUserPlus size={16} />}
            onClick={() => setAdding(true)}
          >
            Додати
          </Button>
        }
      />
      <QueryError error={users.error} />
      <Section
        title={`Користувачів: ${search.query ? `${rows.length} з ${users.data?.length ?? 0}` : (users.data?.length ?? 0)}`}
        loading={users.isPending}
        actions={
          <TextInput
            placeholder='Пошук: імʼя, роль, підрозділ'
            leftSection={<IconSearch size={16} />}
            value={search.value}
            onChange={e => search.setValue(e.currentTarget.value)}
            w={{ base: 200, sm: 340 }}
            aria-label='Пошук користувачів'
          />
        }
      >
        <ScrollArea type='auto'>
          <Table
            miw={720}
            verticalSpacing='sm'
            highlightOnHover
          >
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Імʼя</Table.Th>
                <Table.Th w={190}>Роль</Table.Th>
                <Table.Th>Підрозділ</Table.Th>
                <Table.Th w={96} />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map(u => (
                <Table.Tr key={u.id}>
                  <Table.Td fw={500}>{u.displayName}</Table.Td>
                  <Table.Td>
                    <Tooltip
                      label='Не можна зняти роль адміністратора із себе'
                      disabled={u.id !== me?.id}
                    >
                      <div>
                        <Select
                          size='xs'
                          data={roleOptions}
                          value={u.role}
                          allowDeselect={false}
                          disabled={u.id === me?.id}
                          onChange={v => {
                            if (!v || v === u.role) return
                            const apply = (adminPassword?: string) =>
                              update.mutateAsync({ id: u.id, role: v as Role, adminPassword })
                            const newRole = v as Role
                            if (newRole === "ADMIN")
                              setPromoting({ name: u.displayName, mode: "grant", newRole, apply })
                            else if (u.role === "ADMIN")
                              setPromoting({ name: u.displayName, mode: "revoke", newRole, apply })
                            else apply().catch(fail)
                          }}
                          aria-label='Роль'
                        />
                      </div>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>
                    <SearchSelect
                      size='xs'
                      data={unitOptions}
                      value={u.orgUnitId}
                      allowDeselect={false}
                      onChange={v => v && update.mutate({ id: u.id, orgUnitId: v }, { onError: fail })}
                      aria-label='Підрозділ'
                    />
                  </Table.Td>
                  <Table.Td>
                    <Group
                      gap={4}
                      wrap='nowrap'
                    >
                      <Tooltip label='Перевипустити токен'>
                        <ActionIcon
                          variant='subtle'
                          aria-label='Перевипустити токен'
                          loading={reissue.isPending && reissue.variables?.id === u.id}
                          onClick={() =>
                            u.role === "ADMIN" && u.id !== me?.id
                              ? setTokenFor(u)
                              : reissue.mutate({ id: u.id }, { onSuccess: setToken, onError: fail })
                          }
                        >
                          <IconKey size={18} />
                        </ActionIcon>
                      </Tooltip>
                      {u.id !== me?.id && (
                        <Tooltip label='Видалити користувача'>
                          <ActionIcon
                            variant='subtle'
                            color='danger'
                            aria-label='Видалити користувача'
                            onClick={() => setDeleting(u)}
                          >
                            <IconTrash size={18} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
      </Section>

      <Modal
        opened={adding}
        onClose={() => setAdding(false)}
        title='Новий користувач'
      >
        <form
          onSubmit={e => {
            e.preventDefault()
            if (!form.displayName.trim() || !form.orgUnitId) return
            const data = { displayName: form.displayName.trim(), role: form.role, orgUnitId: form.orgUnitId }
            const apply = (adminPassword?: string) =>
              create.mutateAsync({ ...data, adminPassword }).then(u => {
                setAdding(false)
                setForm({ displayName: "", role: "EXECUTOR", orgUnitId: null })
                setToken(u)
              })
            if (data.role === "ADMIN") setPromoting({ name: data.displayName, mode: "grant", newRole: "ADMIN", apply })
            else apply().catch(fail)
          }}
        >
          <Stack>
            <TextInput
              label='Імʼя'
              value={form.displayName}
              onChange={e => {
                const displayName = e.currentTarget.value
                setForm(f => ({ ...f, displayName }))
              }}
              required
            />
            <Select
              label='Роль'
              data={roleOptions}
              value={form.role}
              onChange={v => v && setForm(f => ({ ...f, role: v as Role }))}
              allowDeselect={false}
            />
            <SearchSelect
              label='Підрозділ'
              data={unitOptions}
              value={form.orgUnitId}
              onChange={v => setForm(f => ({ ...f, orgUnitId: v }))}
              required
            />
            <Group justify='flex-end'>
              <Button
                type='submit'
                loading={create.isPending}
              >
                Створити і видати токен
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Modal
        opened={deleting !== null}
        onClose={closeDelete}
        title='Видалити користувача?'
      >
        <form
          onSubmit={e => {
            e.preventDefault()
            void confirmDelete()
          }}
        >
          <Stack>
            <Text size='sm'>
              Обліковий запис «{deleting?.displayName}» буде видалено: токен перестане діяти, користувач зникне зі
              списків і розсилок. Його дії в журналі та історії заходів збережуться, а персональні призначення перейдуть
              на підрозділ.
            </Text>
            {deletingAdmin && (
              <>
                <Text size='sm'>
                  Це адміністратор: разом з обліковим записом з нього буде знято роль адміністратора.
                </Text>
                {secretInput("Без нього адміністратора видалити не можна")}
              </>
            )}
            <Group justify='flex-end'>
              <Button
                variant='default'
                onClick={closeDelete}
              >
                Скасувати
              </Button>
              <Button
                type='submit'
                variant='light'
                color='danger'
                leftSection={<IconTrash size={16} />}
                disabled={deletingAdmin && !secret}
                loading={granting}
              >
                Видалити
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Modal
        opened={tokenFor !== null}
        onClose={closeTokenFor}
        title='Перевипустити токен адміністратора?'
      >
        <form
          onSubmit={e => {
            e.preventDefault()
            void confirmTokenFor()
          }}
        >
          <Stack>
            <Text size='sm'>
              Поточний токен «{tokenFor?.displayName}» одразу перестане діяти. Новий токен дає повні адміністративні
              права, тому потрібне підтвердження.
            </Text>
            {secretInput("Без нього токен іншого адміністратора не перевипускається")}
            <Group justify='flex-end'>
              <Button
                variant='default'
                onClick={closeTokenFor}
              >
                Скасувати
              </Button>
              <Button
                type='submit'
                leftSection={<IconKey size={16} />}
                disabled={!secret}
                loading={granting}
              >
                Перевипустити
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Modal
        opened={promoting !== null}
        onClose={closeGrant}
        title={
          <Group gap='xs'>
            <IconAlertTriangle
              size={20}
              color='var(--mantine-color-warning-6)'
            />
            {promoting?.mode === "revoke" ? "Зняти роль адміністратора?" : "Надати роль адміністратора?"}
          </Group>
        }
      >
        <Stack>
          {promoting?.mode === "revoke" ? (
            <Text size='sm'>
              Користувач «{promoting.name}» втратить адміністративні права: керування обліковими записами, токенами,
              ролями, підрозділами та налаштуваннями. Нова роль — «{roleMeta[promoting.newRole].label}» — дасть доступ
              лише до її функцій. Повернути роль адміністратора зможе тільки інший адміністратор із секретним паролем.
            </Text>
          ) : (
            <>
              <Text size='sm'>Користувач «{promoting?.name}» отримає повні адміністративні права:</Text>
              <List
                size='sm'
                spacing={4}
              >
                <List.Item>
                  створювати, змінювати й видаляти облікові записи, видавати й перевипускати токени;
                </List.Item>
                <List.Item>призначати будь-які ролі, зокрема інших адміністраторів;</List.Item>
                <List.Item>змінювати підрозділи, довідники та налаштування системи;</List.Item>
                <List.Item>читати весь журнал дій.</List.Item>
              </List>
              <Text size='sm'>
                Водночас він втратить доступ до функцій попередньої ролі: адміністратор не веде програму, не вносить
                виконання і не погоджує заходи. Самостійно зняти з себе цю роль він не зможе — лише інший адміністратор.
              </Text>
            </>
          )}
          <form
            onSubmit={e => {
              e.preventDefault()
              void confirmGrant()
            }}
          >
            <Stack>
              {secretInput(
                promoting?.mode === "revoke"
                  ? "Без нього роль адміністратора зняти не можна"
                  : "Без нього роль адміністратора надати не можна"
              )}
              <Group justify='flex-end'>
                <Button
                  variant='default'
                  onClick={closeGrant}
                >
                  Скасувати
                </Button>
                <Button
                  type='submit'
                  variant='light'
                  color='warning'
                  leftSection={<IconAlertTriangle size={16} />}
                  disabled={!secret}
                  loading={granting}
                >
                  {promoting?.mode === "revoke" ? "Так, зняти роль" : "Так, надати роль"}
                </Button>
              </Group>
            </Stack>
          </form>
        </Stack>
      </Modal>

      <TokenModal
        user={token}
        onClose={() => setToken(null)}
      />
    </>
  )
}
