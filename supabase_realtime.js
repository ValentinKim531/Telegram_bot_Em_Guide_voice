import "https://deno.land/x/dotenv/load.ts";
import { createClient } from '@supabase/supabase-js';

// Инициализация клиента Supabase
const SUPABASE_URL = Deno.env.get('SUPABASE_URL');
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY');
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Функция для обработки вставок
const handleInserts = (payload) => {
  const record = payload.new;
  console.log(`Новое сообщение от пользователя ${record.user_id}: ${record.message}`);
};

// Подписка на вставки в таблице user_messages
const channel = supabase
  .channel('public:user_messages')
  .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'user_messages' }, handleInserts)
  .subscribe();

channel.on('postgres_changes', { event: 'INSERT' }, handleInserts).subscribe();
